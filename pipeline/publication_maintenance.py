"""Recoverable, exact-object date cleanup. Never touches latest or other dates."""
import json
from pathlib import Path
from .agent_shadow import run_lock
from .publication_database import load_artifact, private_root, private_write
from .publication_bundle import encoded, sha

PREFIXES = ('payloads/', 'article_payloads/', 'article_images/', 'article_pdfs/')


def verify(state, plan, storage):
    if sha((state/'plan.json').read_bytes()) != json.loads((state/'plan-hash.json').read_bytes())['sha256']:
        raise ValueError('Cleanup plan hash changed')
    anchor = storage.get(plan['anchor'])
    if anchor is None or sha(anchor) != plan['anchor_sha']:
        raise ValueError('Archive edition changed; cleanup/restore stopped')
    for row in plan['objects']:
        if sha((state/row['before_file']).read_bytes()) != row['before_sha']:
            raise ValueError('Cleanup backup hash changed')


def prune_archive(artifact, state, storage, *, execute=False):
    scope, manifest, _, files = load_artifact(artifact)
    state = private_root(state)
    with run_lock(state):
        path = state/'plan.json'
        if path.exists():
            plan = json.loads(path.read_bytes())
            if plan['artifact_hashes'] != scope['artifact_hashes']:
                raise ValueError('Different cleanup artifact')
        else:
            if any(p.name not in ('.lock', '.run.lock') for p in state.iterdir()):
                raise ValueError('Partial cleanup backup; preserve it')
            anchor = scope['date']+'-manifest.json'
            raw = storage.get(anchor)
            if raw is None or json.loads(raw) != manifest:
                raise ValueError('Archive edition differs from cleanup artifact')
            if storage.get(scope['date']+'.zip') != (Path(artifact)/'reader.zip').read_bytes():
                raise ValueError('Archive ZIP differs from cleanup artifact')
            keep = {scope['date']+'/'+n: b for n, b in files.items() if n.startswith(PREFIXES)}
            # Do not remove leftovers until every authoritative asset is readable.
            for name, data in keep.items():
                if storage.get(name) != data:
                    raise ValueError('Current archive asset mismatch: '+name)
            names = storage.list(scope['date'])
            if len(names) != len(set(names)) or any(not n.startswith(scope['date']+'/') for n in names):
                raise ValueError('Unsafe archive listing')
            extras = [n for n in names if n not in keep and n[len(scope['date'])+1:].startswith(PREFIXES)]
            plan = {**scope, 'anchor': anchor, 'anchor_sha': sha(raw), 'objects': []}
            for i, name in enumerate(extras):
                previous = storage.get(name)
                if previous is None:
                    raise ValueError('Archive changed while backing up')
                filename = f'{i}.before'
                private_write(state/filename, previous)
                plan['objects'].append({'name': name, 'before_file': filename, 'before_sha': sha(previous)})
            private_write(path, encoded(plan))
            private_write(state/'plan-hash.json', encoded({'sha256': sha(path.read_bytes())}))
        verify(state, plan, storage)
        journal_path = state/'journal.json'
        journal = json.loads(journal_path.read_bytes()) if journal_path.exists() else {'deleted': {}}
        if journal.get('restored'):
            raise ValueError('Cleanup restored; new reviewed plan required')
        # Global conflict check before the first deletion.
        for row in plan['objects']:
            data = storage.get(row['name'])
            if data is None and row['name'] not in journal['deleted']:
                raise ValueError('Changed cleanup object: '+row['name'])
            if data is not None and sha(data) != row['before_sha']:
                raise ValueError('Changed cleanup object: '+row['name'])
        if execute:
            for row in plan['objects']:
                verify(state, plan, storage)
                name = row['name']; data = storage.get(name)
                if data is not None:
                    if sha(data) != row['before_sha']:
                        raise ValueError('Changed cleanup object before delete')
                    journal['deleted'][name] = 'attempting'
                    private_write(journal_path, encoded(journal))
                    storage.delete(name)
                if storage.get(name) is not None:
                    raise ValueError('Cleanup delete readback mismatch')
                journal['deleted'][name] = 'complete'
                private_write(journal_path, encoded(journal))
            journal['verified'] = True
            private_write(journal_path, encoded(journal))
        return plan


def restore_pruned(state, storage):
    state = private_root(state)
    with run_lock(state):
        plan = json.loads((state/'plan.json').read_bytes())
        verify(state, plan, storage)
        path = state/'journal.json'
        journal = json.loads(path.read_bytes())
        for row in plan['objects']:
            data = storage.get(row['name'])
            if data is not None and sha(data) != row['before_sha']:
                raise ValueError('Changed cleanup object; no restore')
        for row in plan['objects']:
            if row['name'] not in journal['deleted']:
                continue
            verify(state, plan, storage)
            data = storage.get(row['name'])
            if data is None:
                storage.put(row['name'], (state/row['before_file']).read_bytes())
            if storage.get(row['name']) != (state/row['before_file']).read_bytes():
                raise ValueError('Cleanup restore mismatch')
        journal['restored'] = True
        private_write(path, encoded(journal))
        return plan
