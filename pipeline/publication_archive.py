"""Python-only dated archive backup/apply/rollback. Never writes latest.

Private state is durable across machines when securely transferred. Every write
has a before-image and attempt marker; uncertain uploads only retry READBACK.
"""
import json
import time
from pathlib import Path
from urllib.parse import quote

import requests
from .agent_shadow import run_lock
from .publication_database import load_artifact, private_root, private_write
from .publication_bundle import encoded, sha

BUCKET = 'redesign-daily-content'


class ArchiveStorage:
    def __init__(self, url, key):
        from .publication_database import PROJECT
        if url.rstrip('/') != f'https://{PROJECT}.supabase.co':
            raise ValueError('Unsupported archive project')
        self.base = url.rstrip('/')+'/storage/v1/object/'+BUCKET+'/'
        self.headers = {'Authorization': 'Bearer '+key, 'apikey': key}

    def get(self, name):
        response = requests.get(self.base+quote(name, safe='/'), headers=self.headers,
                                params={'publication_readback': str(time.time_ns())}, timeout=30, allow_redirects=False)
        if response.status_code == 404:
            return None
        # Supabase Storage sometimes uses 400 with a JSON 404 code for not found.
        if response.status_code == 400:
            try:
                error = response.json()
                if str(error.get('statusCode')) == '404' and error.get('error') == 'not_found':
                    return None
            except ValueError:
                pass
        response.raise_for_status(); return response.content

    def put(self, name, data):
        content_type = ('application/pdf' if name.endswith('.pdf') else 'application/zip' if name.endswith('.zip') else 'application/json' if name.endswith('.json') else 'image/webp')
        response = requests.post(self.base+quote(name, safe='/'), data=data,
                    headers={**self.headers, 'x-upsert': 'true', 'Content-Type': content_type}, timeout=60)
        response.raise_for_status()

    def delete(self, name):
        # Deletes ONE exact newly created object, never a date folder.
        response = requests.delete(self.base.rstrip('/'),
            json={'prefixes': [name]}, headers=self.headers, timeout=30)
        response.raise_for_status()

    def list(self, prefix):
        """Read exact files recursively under one date, with bounded pagination."""
        from datetime import date
        if date.fromisoformat(prefix).isoformat() != prefix:
            raise ValueError('One ISO archive date required')
        pending, result = [prefix], []
        while pending:
            folder = pending.pop()
            for offset in range(0, 10000, 100):
                response = requests.post(self.base.replace('/object/', '/object/list/').rstrip('/'),
                    headers=self.headers, json={'prefix': folder, 'limit': 100, 'offset': offset,
                        'sortBy': {'column': 'name', 'order': 'asc'}}, timeout=30, allow_redirects=False)
                response.raise_for_status()
                rows = response.json()
                if not isinstance(rows, list):
                    raise ValueError('Invalid Storage list')
                for row in rows:
                    name = row['name']
                    if not name or '/' in name or name in ('.', '..') or '\\' in name:
                        raise ValueError('Unsafe Storage object name')
                    path = folder+'/'+name
                    if row.get('id') is None:
                        pending.append(path)
                    else:
                        result.append(path)
                if len(result)+len(pending) > 10000:
                    raise ValueError('Archive listing budget exceeded')
                if len(rows) < 100:
                    break
            else:
                raise ValueError('Archive listing pagination budget exceeded')
        return sorted(result)


def targets(artifact, storage):
    scope, manifest, _, files = load_artifact(artifact)
    result = {scope['date']+'.zip': (Path(artifact)/'reader.zip').read_bytes(),
              scope['date']+'-manifest.json': encoded(manifest)}
    result.update({scope['date']+'/'+name: data for name, data in files.items()
                   if name.startswith(('payloads/', 'article_payloads/', 'article_images/', 'article_pdfs/'))})
    raw_index = storage.get('archive-index.json')
    if raw_index is None:
        raise ValueError('Missing archive index; do not silently reset history')
    index = json.loads(raw_index)
    from datetime import date
    dates = index.get('dates')
    if not isinstance(dates, list) or any(not isinstance(d, str) or date.fromisoformat(d).isoformat()!=d for d in dates):
        raise ValueError('Invalid archive index')
    if scope['date'] not in dates:
        index['dates'] = sorted(set(dates+[scope['date']]), reverse=True)[:30]
        result['archive-index.json'] = encoded(index)
    return scope, result


def prepare_archive(artifact, state, storage):
    state = private_root(state)
    with run_lock(state):
        marker = state/'prepared.json'
        scope, _, _, _ = load_artifact(artifact)
        if marker.exists():
            plan = json.loads(marker.read_bytes())
            if plan['artifact_hashes'] != scope['artifact_hashes']:
                raise ValueError('Archive input changed; preserve original backup')
            verify_plan(state, plan); return plan
        if any(p.name not in ('.lock', '.run.lock') for p in state.iterdir()):
            raise ValueError('Partial archive backup; preserve before-images and inspect')
        scope, objects = targets(artifact, storage)
        plan = {**scope, 'objects': []}
        for i, (name, data) in enumerate(sorted(objects.items())):
            previous = storage.get(name)
            before, after = f'{i}.before', f'{i}.after'
            if previous is not None:
                private_write(state/before, previous)
            private_write(state/after, data)
            plan['objects'].append({'name': name, 'before_file': before if previous is not None else None,
                'before_sha': sha(previous) if previous is not None else None,
                'after_file': after, 'after_sha': sha(data)})
        private_write(marker, encoded(plan))
        private_write(state/'plan-sha.json', encoded({'sha256': sha(marker.read_bytes())}))
        return plan


def verify_plan(state, plan):
    marker = state/'prepared.json'
    if json.loads((state/'plan-sha.json').read_bytes())['sha256'] != sha(marker.read_bytes()):
        raise ValueError('Archive plan hash changed')
    for row in plan['objects']:
        for kind in ('before', 'after'):
            name = row[kind+'_file']
            if name is not None and sha((state/name).read_bytes()) != row[kind+'_sha']:
                raise ValueError('Archive backup/payload hash changed')


def apply_archive(artifact, state, storage):
    state = private_root(state)
    plan = prepare_archive(artifact, state, storage)
    with run_lock(state):
        verify_plan(state, plan)
        journal_path = state/'journal.json'
        journal = json.loads(journal_path.read_bytes()) if journal_path.exists() else {'writes': {}}
        if journal.get('rollback_started'):
            raise ValueError('Archive rollback started; never reapply')
        # Global preflight BEFORE any uploads; stop on a competing writer.
        for row in plan['objects']:
            remote = storage.get(row['name']); actual = sha(remote) if remote is not None else None
            if actual not in {row['before_sha'], row['after_sha']}:
                raise ValueError('Competing archive writer: '+row['name'])
        for row in plan['objects']:
            name = row['name']; remote = storage.get(name)
            actual = sha(remote) if remote is not None else None
            if actual == row['after_sha']:
                journal['writes'][name] = 'complete'
            elif journal['writes'].get(name) in ('attempting', 'complete'):
                raise ValueError('Archive upload uncertain; inspect saved state: '+name)
            else:
                if actual != row['before_sha']:
                    raise ValueError('Competing archive writer: '+name)
                journal['writes'][name] = 'attempting'; private_write(journal_path, encoded(journal))
                storage.put(name, (state/row['after_file']).read_bytes())
                remote = storage.get(name)
                if remote is None or sha(remote) != row['after_sha']:
                    raise ValueError('Archive readback mismatch: '+name)
                journal['writes'][name] = 'complete'
            private_write(journal_path, encoded(journal))
        journal['verified'] = True; private_write(journal_path, encoded(journal))
        return plan


def rollback_archive(state, storage):
    state = private_root(state)
    with run_lock(state):
        plan = json.loads((state/'prepared.json').read_bytes()); verify_plan(state, plan)
        path = state/'journal.json'
        journal = json.loads(path.read_bytes()) if path.exists() else {'writes': {}}
        rows = [r for r in plan['objects'] if r['name'] in journal['writes']]
        for row in rows:
            remote = storage.get(row['name']); actual = sha(remote) if remote is not None else None
            if actual not in {row['before_sha'], row['after_sha']}:
                raise ValueError('Competing archive writer; no rollback: '+row['name'])
        journal['rollback_started'] = True; private_write(path, encoded(journal))
        for row in reversed(rows):
            remote = storage.get(row['name']); actual = sha(remote) if remote is not None else None
            if actual == row['before_sha']:
                continue
            if row['before_file'] is None:
                storage.delete(row['name'])
            else:
                storage.put(row['name'], (state/row['before_file']).read_bytes())
            remote = storage.get(row['name']); actual = sha(remote) if remote is not None else None
            if actual != row['before_sha']:
                raise ValueError('Archive rollback readback mismatch')
        journal['rolled_back'] = True; private_write(path, encoded(journal))
        return plan
