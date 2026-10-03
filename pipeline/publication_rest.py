"""Legacy service-role/Data API writer with durable per-row recovery.

No arbitrary SQL endpoint, RPC/schema installation or PostgreSQL password.
REST requests are individually transactional, NOT a four-table transaction.
Before/after checks detect conflicts but do not provide cross-writer CAS.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path

import requests
from .publication_database import (PROJECT, TABLES, ManagementClient, canonical,
                                  private_write, verify_prepared)
from .publication_bundle import encoded


def matches(actual, expected, table):
    if actual is None or expected is None:
        return actual is expected
    # New inserts receive server defaults. Compare all planned fields; an old
    # before-image contains every column and therefore detects other changes.
    projected = {k: actual.get(k) for k in expected}
    return canonical([projected], table) == canonical([expected], table)


class RestClient(ManagementClient):
    def __init__(self, url=None, key=None):
        self.project = PROJECT
        url = url or os.environ.get('SUPABASE_URL') or f'https://{PROJECT}.supabase.co'
        if url.rstrip('/') != f'https://{PROJECT}.supabase.co':
            raise ValueError('Unsupported database project')
        key = key or os.environ['SUPABASE_SERVICE_KEY']
        self.base = url.rstrip('/')+'/rest/v1/'
        self.headers = {'apikey': key, 'Authorization': 'Bearer '+key}

    def rows(self, table, filters):
        if table not in TABLES:
            raise ValueError('Unsupported table')
        result = []
        for offset in range(0,10000,500):
            response = requests.get(self.base+table, headers=self.headers,
                params={**filters,'select':'*','order':'id.asc','limit':500,'offset':offset},
                timeout=30, allow_redirects=False)
            response.raise_for_status(); batch = response.json()
            if not isinstance(batch,list):
                raise ValueError('Data API must return rows')
            result.extend(batch)
            if len(batch)<500:
                return result
        raise ValueError('Data API read budget exceeded')

    def preflight(self):
        # Only read operations. GET proves visibility, NOT write permission;
        # actual writes are subsequently checked and their results verified.
        for table in TABLES:
            self.rows(table, {'id':'is.null'})

    def snapshot(self, scope):
        result = {}
        for table in TABLES:
            filters = {'id':'eq.'+scope['run_id']} if table=='redesign_runs' else (
                {'id':'in.('+','.join(map(str,scope['source_ids']))+')'}
                if table=='redesign_source_configs' else {'published_date':'eq.'+scope['date']})
            result[table] = self.rows(table,filters) if table!='redesign_source_configs' or scope['source_ids'] else []
        return {'columns':{},'rows':result}

    @contextmanager
    def publication_lock(self):
        # Caller owns a local durable-state lock. No misleading claim of a
        # remote advisory lock/lease; unrelated machines/writers are unguarded.
        yield

    def mutate(self, table, old, new):
        rid = (new or old)['id']
        headers = {**self.headers,'Prefer':'return=representation'}
        if new is None:
            response = requests.delete(self.base+table,params={'id':'eq.'+str(rid)},
                headers=headers,timeout=60,allow_redirects=False)
        elif old is None:
            payload = {k:v for k,v in new.items() if k!='doc_tsv'}
            # Do not overwrite a competing insert. Readback must match target.
            response = requests.post(self.base+table,params={'on_conflict':'id'},json=payload,
                headers={**headers,'Prefer':'resolution=ignore-duplicates,return=representation'},
                timeout=60,allow_redirects=False)
        else:
            payload = {k:v for k,v in new.items() if k not in ('id','doc_tsv') and old.get(k)!=v}
            if not payload:
                return
            response = requests.patch(self.base+table,params={'id':'eq.'+str(rid)},json=payload,
                headers=headers,timeout=60,allow_redirects=False)
        response.raise_for_status()

    def verify_database(self, state):
        root = Path(state); verify_prepared(root)
        scope = json.loads((root/'scope.json').read_bytes())
        expected = json.loads((root/'after.json').read_bytes())
        self.check_target(self.snapshot(scope)['rows'], expected)
        return True

    def check_target(self, actual, expected):
        for table in TABLES:
            a = {str(r['id']):r for r in actual[table]}
            e = {str(r['id']):r for r in expected[table]}
            if set(a)!=set(e) or any(not matches(a[k],e[k],table) for k in e):
                raise ValueError('Database readback mismatch: '+table)

    def apply_prepared(self, root, restore=False):
        root = Path(root); ready = verify_prepared(root)
        execution = root/'execution.json'
        prior = json.loads(execution.read_bytes()) if execution.exists() else {}
        if prior.get('status') in ('attempting','rollback_attempting') and prior.get('transport')!='supabase-service-role-rest':
            raise ValueError('SQL outcome uncertain; do not switch transport during recovery')
        scope = json.loads((root/'scope.json').read_bytes())
        before = json.loads((root/'before.json').read_bytes())
        after = json.loads((root/'after.json').read_bytes())
        direction = 'rollback' if restore else 'apply'
        path = root/'rest-execution.json'
        journal = json.loads(path.read_bytes()) if path.exists() else {
            'transport':'supabase-service-role-rest','artifact_hashes':ready['artifact_hashes'],
            'apply':{},'rollback':{}}
        if journal['artifact_hashes']!=ready['artifact_hashes']:
            raise ValueError('REST journal belongs to another edition')
        if journal['rollback'] and not restore:
            raise ValueError('Rollback started; do not reapply')
        current = self.snapshot(scope)['rows']
        # Check ALL tables before ANY mutation; extra/missing/unrelated values
        # stop without deleting another publisher's date slots.
        for table in TABLES:
            b = {str(r['id']):r for r in before[table]}
            a = {str(r['id']):r for r in after[table]}
            live = {str(r['id']):r for r in current[table]}
            if set(live)-set(b)-set(a):
                raise ValueError('Foreign date rows: '+table)
            for rid in set(b)|set(a):
                if not (matches(live.get(rid),b.get(rid),table) or matches(live.get(rid),a.get(rid),table)):
                    raise ValueError('Changed records: '+table)
        target, origin = (before,after) if restore else (after,before)
        tables = reversed(TABLES) if restore else TABLES
        for table in tables:
            wanted = {str(r['id']):r for r in target[table]}
            old = {str(r['id']):r for r in origin[table]}
            for rid in sorted(set(wanted)|set(old)):
                rows = self.rows(table,{'id':'eq.'+rid})
                if len(rows)>1:
                    raise ValueError('Duplicate primary ID')
                live = rows[0] if rows else None
                new = wanted.get(rid); key = table+'/'+rid
                if matches(live,new,table):
                    journal[direction][key] = 'complete'
                    private_write(path,encoded(journal));continue
                if not matches(live,old.get(rid),table):
                    raise ValueError('Changed records immediately before write: '+table)
                if journal[direction].get(key)=='attempting':
                    raise ValueError('REST outcome uncertain; inspect original before/after, do not resend')
                journal[direction][key]='attempting';private_write(path,encoded(journal))
                try:
                    self.mutate(table,live,new)
                except requests.HTTPError as exc:
                    if exc.response is not None and 400<=exc.response.status_code<500:
                        journal[direction][key]='failed_not_executed';private_write(path,encoded(journal))
                    raise
                rows = self.rows(table,{'id':'eq.'+rid})
                actual = rows[0] if rows else None
                if not matches(actual,new,table):
                    raise ValueError('Database mutation readback mismatch: '+table)
                journal[direction][key]='complete';private_write(path,encoded(journal))
        self.check_target(self.snapshot(scope)['rows'],target)
        private_write(root/'execution.json',encoded({'status':'rolled_back' if restore else 'committed',
            'transport':'supabase-service-role-rest','zip_sha256':ready['zip_sha256']}))
        return ready
