"""Opt-in live rollback drill: isolated Storage prefix and an EMPTY old DB date.

No models, website dispatch, live latest, source-config mutation or schema changes.
Private before/after SQL and Storage recovery remain on disk. Never auto-rerun an
unfinished drill in a different directory: inspect its saved state first.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid
from .publication_archive import ArchiveStorage, apply_archive, rollback_archive
from .publication_bundle import encoded, sha
from .publication_database import PROJECT, load_artifact, private_root, private_write, commit, rollback
from .publication_rest import RestClient
from .website_release import LatestRelease, zip_files


class IsolatedStorage:
    def __init__(self, storage, prefix):
        self.storage, self.prefix = storage, prefix
    def get(self, name): return self.storage.get(self.prefix+name)
    def put(self, name, data): return self.storage.put(self.prefix+name, data)
    def delete(self, name): return self.storage.delete(self.prefix+name)
    def download(self, name):
        data = self.get(name)
        if data is None: raise ValueError('Missing drill object')
        return data
    def upload(self, *, path, file, file_options): self.put(path, file)


def drill(artifact, state, *, execute=False):
    if not execute:
        raise ValueError('Live drill requires --execute')
    state = private_root(state)
    if any(state.iterdir()):
        raise ValueError('Drill state must be new; preserve unfinished recovery state')
    original_scope, original_manifest, records, files = load_artifact(artifact)
    day = '1900-01-01'
    storage = ArchiveStorage(f'https://{PROJECT}.supabase.co', os.environ['SUPABASE_SERVICE_KEY'])
    client = RestClient()
    if client.rows('redesign_stories', {'published_date': 'eq.'+day}) or client.rows('redesign_search_index', {'published_date': 'eq.'+day}) or client.rows('redesign_runs', {'run_date': 'eq.'+day}):
        raise ValueError('Drill date occupied; no mutation')
    live_before = {name: storage.get(name) for name in ('latest.zip', 'latest-manifest.json')}
    business_before = {table: client.rows(table, {'published_date': 'eq.'+original_scope['date']})
                       for table in ('redesign_stories', 'redesign_search_index')}
    prefix = 'maintenance-tests/rollback-'+str(uuid.uuid4())+'/'
    private_write(state/'scope.json', encoded({'date': day, 'prefix': prefix, 'source_ids': [],
        'website_dispatch': False, 'original_latest': {n: sha(b) for n,b in live_before.items()}}))
    isolated = IsolatedStorage(storage, prefix)
    def replace(value):
        if isinstance(value, str): return value.replace(original_scope['date'], day)
        if isinstance(value, list): return [replace(v) for v in value]
        if isinstance(value, dict): return {k: replace(v) for k,v in value.items()}
        return value
    remapped = {}
    for name, data in files.items():
        name = name.replace(original_scope['date'], day)
        remapped[name] = encoded(replace(json.loads(data))) if name.endswith('.json') else data
    rows = replace(records)
    for row in rows: row['source_config_id'] = None
    data = zip_files(remapped)
    manifest = {**replace(original_manifest), 'version': day, 'zip_sha256': sha(data), 'zip_bytes': len(data),
                'files': {n: sha(b) for n,b in sorted(remapped.items())}}
    target = state/'artifact'; target.mkdir()
    private_write(target/'reader.zip', data); private_write(target/'latest-manifest.json', encoded(manifest))
    private_write(target/'records.json', encoded(rows))
    scope = load_artifact(target)[0]
    initial = {'latest.zip': data, 'latest-manifest.json': encoded(manifest),
        'archive-index.json': encoded({'dates': ['1899-01-01']}), day+'.zip': b'drill-before-zip'}
    for name, content in initial.items(): isolated.put(name, content)
    # Test the exact production latest backup/replace/rollback code over real Storage.
    release = LatestRelease(state/'latest', isolated)
    release.backup()
    alternative = zip_files({**remapped, 'assets/rollback-drill.txt': b'test'})
    other_manifest = {**manifest, 'zip_sha256': sha(alternative), 'zip_bytes': len(alternative),
        'files': {**manifest['files'], 'assets/rollback-drill.txt': sha(b'test')}}
    release.publish(alternative, other_manifest, acknowledge_slots=True)
    release.rollback(); release.rollback()
    if isolated.get('latest.zip') != data or json.loads(isolated.get('latest-manifest.json')) != manifest:
        raise ValueError('Live latest rollback drill failed')

    plan = apply_archive(target, state/'archive', isolated)
    def verify_archive(_):
        for row in plan['objects']:
            if sha(isolated.get(row['name'])) != row['after_sha']:
                raise ValueError('Live drill archive hash mismatch')
    client.verify_archive = verify_archive
    # Deliberately lose one successful mutation response, then prove readback resume.
    original_mutate = client.mutate
    calls = []
    def lose_once(table, before, after):
        original_mutate(table, before, after)
        calls.append((table, str((after or before)['id'])))
        if len(calls) == 1:
            import requests
            raise requests.ReadTimeout('drill: simulate lost successful response')
    client.mutate = lose_once
    try:
        commit(target, state/'database', client)
    except Exception as exc:
        import requests
        if not isinstance(exc, requests.ReadTimeout): raise
    commit(target, state/'database', client)
    client.verify_database(state/'database')
    if len(calls) != len(set(calls)):
        raise ValueError('Duplicate database mutation on resume')
    rollback(state/'database', client); rollback(state/'database', client)
    if any(client.snapshot(scope)['rows'].values()):
        raise ValueError('Drill database rollback left rows')
    rollback_archive(state/'archive', isolated); rollback_archive(state/'archive', isolated)
    for row in plan['objects']:
        actual = isolated.get(row['name'])
        if (sha(actual) if actual is not None else None) != row['before_sha']:
            raise ValueError('Drill archive rollback mismatch')
    for name, content in initial.items():
        if isolated.get(name) != content: raise ValueError('Drill seed not restored')
    for name in initial:
        isolated.delete(name)
        if isolated.get(name) is not None: raise ValueError('Drill seed cleanup failed')
    if any(storage.get(name) != data for name, data in live_before.items()):
        raise ValueError('Production latest changed during drill')
    if any(client.rows(table, {'published_date': 'eq.'+original_scope['date']}) != old for table, old in business_before.items()):
        raise ValueError('Production rows changed during drill')
    report = {'ok': True, 'date': day, 'storage_prefix': prefix, 'latest_rollback': True,
        'archive_rollback': True, 'database_rollback': True, 'lost_response_resume': True,
        'repeated_rollback': True, 'test_objects_removed': True, 'production_unchanged': True,
        'verified_at': datetime.now(timezone.utc).isoformat()}
    private_write(state/'result.json', encoded(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-dir', type=Path, required=True)
    parser.add_argument('--state-dir', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(drill(args.artifact_dir, args.state_dir, execute=args.execute)))
        return 0
    except Exception as exc:
        print(json.dumps({'ok': False, 'error_class': type(exc).__name__, 'state_dir': str(args.state_dir)}))
        return 1


if __name__ == '__main__': raise SystemExit(main())
