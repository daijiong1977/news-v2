"""Automatic paired SQL regressions; no real database or publication writes."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import uuid

import pytest

from pipeline.test_publication_bundle import full_bundle
from pipeline.website_release import build_reader


def fixture(tmp_path, monkeypatch, day=None):
    from pipeline.publication_bundle import unpack
    bundle, _ = full_bundle(tmp_path, monkeypatch)
    shell = tmp_path/'shell'; shell.mkdir(); (shell/'index.html').write_text('official')
    result = build_reader(bundle.read_bytes(), shell, 'a'*40)
    artifact = tmp_path/'artifact'; artifact.mkdir()
    (artifact/'reader.zip').write_bytes(result['zip'])
    (artifact/'latest-manifest.json').write_text(json.dumps(result['manifest']))
    (artifact/'records.json').write_text(json.dumps(result['records']))
    columns = {t: [] for t in ('redesign_runs','redesign_stories','redesign_search_index','redesign_source_configs')}
    return artifact, result, columns


class Client:
    def __init__(self): self.reads=0; self.executed=[]
    def snapshot(self, scope):
        self.reads += 1
        return {'columns': {}, 'rows': {
            'redesign_runs': [], 'redesign_stories': [], 'redesign_search_index': [],
            'redesign_source_configs': [{'id':i,'cadence_days':2,'last_used_at':None,'next_pickup_at':None}
                                       for i in scope['source_ids']]}}
    def execute(self, sql): self.executed.append(sql)
    def verify_archive(self, artifact): pass


def test_pair_generated_before_any_execution_and_resume_reuses_snapshot(tmp_path, monkeypatch):
    from pipeline.publication_database import commit, prepare, verify_prepared
    artifact, result, _=fixture(tmp_path, monkeypatch)
    client=Client(); state=tmp_path/'private-state'
    prepare(artifact,state,client)
    assert (state/'apply.sql').is_file() and (state/'rollback.sql').is_file()
    assert client.executed==[]
    initial=(state/'rollback.sql').read_bytes()
    prepare(artifact,state,client)
    assert client.reads==1 and (state/'rollback.sql').read_bytes()==initial
    assert verify_prepared(state)['zip_sha256']==result['manifest']['zip_sha256']
    commit(artifact,state,client)
    assert client.reads==1 and len(client.executed)==1
    commit(artifact,state,client)
    assert len(client.executed)==1


@pytest.mark.parametrize('name',['apply.sql','rollback.sql','before.json','after.json'])
def test_corrupt_pair_blocks_execution(tmp_path,monkeypatch,name):
    from pipeline.publication_database import prepare,commit
    artifact,_,_=fixture(tmp_path,monkeypatch);client=Client();state=tmp_path/'state'
    prepare(artifact,state,client);(state/name).write_bytes(b'tampered')
    with pytest.raises(ValueError,match='hash'):commit(artifact,state,client)
    assert client.executed==[] and client.reads==1


def test_failed_sql_keeps_attempting_and_never_resends_or_regenerates(tmp_path,monkeypatch):
    from pipeline.publication_database import commit
    artifact,_,_=fixture(tmp_path,monkeypatch);state=tmp_path/'state';client=Client()
    def uncertain(sql): client.executed.append(sql);raise TimeoutError()
    client.execute=uncertain
    with pytest.raises(TimeoutError):commit(artifact,state,client)
    with pytest.raises(ValueError,match='uncertain'):commit(artifact,state,client)
    assert client.reads==1 and len(client.executed)==1
    assert json.loads((state/'execution.json').read_text())['status']=='attempting'


def test_missing_source_and_foreign_day_snapshot_fail_closed(tmp_path,monkeypatch):
    from pipeline.publication_database import prepare
    artifact,_,_=fixture(tmp_path,monkeypatch);client=Client()
    client.snapshot=lambda scope:{'columns':{},'rows':{'redesign_runs':[],'redesign_stories':[{'id':str(uuid.uuid4()),'published_date':'1999-01-01'}], 'redesign_search_index':[], 'redesign_source_configs':[]}}
    with pytest.raises(ValueError):prepare(artifact,tmp_path/'state',client)
    assert not (tmp_path/'state/prepared.json').exists()


def test_same_day_preserves_uuid_and_source_cadence_and_rollback_targets(tmp_path,monkeypatch):
    from pipeline.publication_database import prepare
    artifact,result,_=fixture(tmp_path,monkeypatch);client=Client();original=client.snapshot
    sid=result['records'][0]['payload_story_id'];story_id=str(uuid.uuid4())
    def snap(scope):
        value=original(scope)
        r=result['records'][0]
        value['rows']['redesign_stories']=[{'id':story_id,'payload_story_id':sid,'published_date':scope['date'],
            'category':r['category'],'story_slot':r['story_slot'],'created_at':'2020-01-01T00:00:00+00:00','run_id':str(uuid.uuid4())}]
        for row in value['rows']['redesign_source_configs']:
            row.update(last_used_at='2099-01-01T00:00:00+00:00',next_pickup_at='2099-01-03')
        return value
    client.snapshot=snap;state=tmp_path/'state';prepare(artifact,state,client)
    after=json.loads((state/'after.json').read_text())
    assert next(r for r in after['redesign_stories'] if r['payload_story_id']==sid)['id']==story_id
    assert all(r['next_pickup_at']=='2099-01-03' for r in after['redesign_source_configs'])
    sql=(state/'rollback.sql').read_text()
    assert 'Changed records' in sql and 'disable trigger redesign_search_index_tsv_update' in sql
    assert 'redesign_reading' not in sql and 'latest.zip' not in sql


def test_partial_preparation_never_recaptures_or_executes(tmp_path,monkeypatch):
    from pipeline.publication_database import prepare
    artifact,_,_=fixture(tmp_path,monkeypatch);client=Client();state=tmp_path/'state';state.mkdir()
    (state/'before.json').write_text('{}')
    with pytest.raises(ValueError,match='partial'):prepare(artifact,state,client)
    assert client.reads==0 and client.executed==[]


def test_archive_failure_keeps_pair_but_never_attempts_db(tmp_path,monkeypatch):
    from pipeline.publication_database import commit
    artifact,_,_=fixture(tmp_path,monkeypatch);client=Client();state=tmp_path/'state'
    def fail(artifact):raise ValueError('archive mismatch')
    client.verify_archive=fail
    with pytest.raises(ValueError,match='archive'):commit(artifact,state,client)
    assert (state/'rollback.sql').exists() and not (state/'execution.json').exists()
    assert client.executed==[]


def test_private_state_permissions_and_reject_git_or_work(tmp_path,monkeypatch):
    from pipeline.publication_database import prepare
    artifact,_,_=fixture(tmp_path,monkeypatch);client=Client();state=tmp_path/'private'
    prepare(artifact,state,client)
    assert state.stat().st_mode & 0o777==0o700
    assert (state/'rollback.sql').stat().st_mode & 0o777==0o600
    with pytest.raises(ValueError,match='private'):prepare(artifact,tmp_path/'work'/'backup',client)


def test_sql_delimiters_cannot_be_injected_by_source_text():
    from pipeline.publication_database import TABLES,sql_pair
    before={t:[] for t in TABLES};after=copy.deepcopy(before)
    after['redesign_runs']=[{'id':str(uuid.uuid4()),'notes':"'; $checks$ END; DELETE FROM redesign_stories; --"}]
    scope={'date':'2026-10-03','source_ids':[],'run_id':after['redesign_runs'][0]['id']}
    apply,rollback=sql_pair(before,after,scope)
    assert 'DO $checks$' not in apply and 'DO $b' in apply


@pytest.mark.skipif(shutil.which('deno') is None,reason='Offline PostgreSQL WASM runtime unavailable')
def test_generated_sql_executes_and_rolls_back_in_postgres(tmp_path,monkeypatch):
    from pipeline.publication_database import prepare
    artifact,_,_=fixture(tmp_path,monkeypatch);state=tmp_path/'sql'
    prepare(artifact,state,Client())
    script=Path(__file__).with_name('test_publication_database_sql.ts')
    result=subprocess.run(['deno','run','--allow-read',str(script),str(state)],capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    report=json.loads(result.stdout.strip().splitlines()[-1])
    assert report['pass'] is True and report['assertions']==10


def test_rollback_uses_original_file_and_never_recaptures(tmp_path,monkeypatch):
    from pipeline.publication_database import commit,rollback
    artifact,_,_=fixture(tmp_path,monkeypatch);client=Client();state=tmp_path/'state'
    commit(artifact,state,client);expected=(state/'rollback.sql').read_text()
    rollback(state,client);rollback(state,client)
    assert client.executed[-1]==expected and len(client.executed)==2 and client.reads==1
    with pytest.raises(ValueError,match='uncertain'):commit(artifact,state,client)


def test_cadence_uses_edition_et_day_not_utc_date(tmp_path,monkeypatch):
    from pipeline.publication_database import prepare
    artifact,result,_=fixture(tmp_path,monkeypatch);client=Client()
    # 02:00 UTC is still the previous ET edition date.
    from datetime import date,timedelta
    day=date.fromisoformat(result['manifest']['version']);following=day+timedelta(days=1)
    result['manifest']['packed_at']=following.isoformat()+'T02:00:00+00:00'
    (artifact/'latest-manifest.json').write_text(json.dumps(result['manifest']))
    state=tmp_path/'state';prepare(artifact,state,client)
    after=json.loads((state/'after.json').read_text())
    assert all(r['next_pickup_at']==(day+timedelta(days=2)).isoformat() for r in after['redesign_source_configs'])
