"""All-Python/Agent JSON orchestration tests. No real models/database/network."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pipeline import agent_shadow as runner
from pipeline.test_kidsnews_groups import prepared
from pipeline.test_agent_shadow_source_first import combined_answer
from pipeline.test_publication_database import fixture, Client


class Provider:
    def __init__(self): self.calls=[]
    def complete(self,payload,timeout):
        self.calls.append(payload)
        material=json.loads(payload['messages'][1]['content'])
        if 'candidates' in material:
            value={'order':[r['id'] for r in material['candidates']], 'reason':'Child relevance'}
        else:
            value=combined_answer()
        return {'choices':[{'message':{'content':json.dumps(value)},'finish_reason':'stop'}], 'usage':{}}


def test_cursor_json_adapter_uses_stdin_empty_workspace_no_shell_no_db_env(monkeypatch):
    from pipeline.cursor_json import CursorJSONProvider
    monkeypatch.setenv('SUPABASE_SERVICE_KEY','do-not-pass')
    monkeypatch.setenv('KIDSNEWS_DATABASE_URL','do-not-pass')
    def call(command,**kwargs):
        assert command[1:4]==['-p','--mode','ask']
        assert '--force' not in command and '--resume' not in command
        assert 'do-not-pass' not in str(kwargs['env'])
        assert not list(Path(kwargs['cwd']).iterdir())
        assert 'messages' in kwargs['input']
        return SimpleNamespace(returncode=0,stdout=json.dumps({'result':'{"ok":true}'}))
    monkeypatch.setattr('subprocess.run',call)
    value=CursorJSONProvider('grok-4.7-low','agent').complete({'messages':[{'role':'user','content':'JSON'}]})
    assert json.loads(value['choices'][0]['message']['content'])=={'ok':True}


def test_cursor_rejects_non_json_error_or_truncated(monkeypatch):
    from pipeline.cursor_json import CursorJSONProvider
    for value in ({'result':'not JSON'},{'is_error':True,'result':'{}'},
                  {'choices':[{'message':{'content':'{}'},'finish_reason':'length'}]}):
        monkeypatch.setattr('subprocess.run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=json.dumps(value)))
        with pytest.raises(ValueError): CursorJSONProvider(binary='agent').complete({'messages':[{}]})


def test_api_editor_nine_once_and_resume_no_model_calls(tmp_path,monkeypatch):
    from pipeline.kidsnews_api_editor import edit_groups
    prepared(tmp_path,monkeypatch);provider=Provider();identity={'type':'fake','model':'grok'}
    assert edit_groups(tmp_path,provider,identity)['counts']=={c:3 for c in runner.CATS}
    assert len(provider.calls)==12
    assert edit_groups(tmp_path,provider,identity)['ok'] and len(provider.calls)==12
    monkeypatch.setattr(runner,'ask',lambda *a,**k:pytest.fail('No interactive model handoff'))
    assert runner.advance(tmp_path)['counts']=={'news':3,'science':3,'fun':3}


def test_api_editor_provider_and_accepted_answer_tamper_stop(tmp_path,monkeypatch):
    from pipeline.kidsnews_api_editor import edit_groups
    prepared(tmp_path,monkeypatch);provider=Provider();identity={'type':'fake','model':'grok'}
    edit_groups(tmp_path,provider,identity)
    with pytest.raises(ValueError,match='provider changed'):edit_groups(tmp_path,provider,{'type':'fake','model':'other'})
    path=next((tmp_path/'api-tasks').glob('*/**/answer.json'));path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(RuntimeError):edit_groups(tmp_path,provider,identity)


def test_agent_uncertain_call_not_resent(tmp_path):
    from pipeline.kidsnews_api_editor import CachedJSON
    provider=Provider()
    def fail(*a):raise TimeoutError()
    provider.complete=fail;ask=CachedJSON(tmp_path,provider,{'model':'test'})
    with pytest.raises(TimeoutError):ask(tmp_path,'one','prompt',{},lambda v:[])
    with pytest.raises(ValueError,match='uncertain'):ask(tmp_path,'one','prompt',{},lambda v:[])


class Storage:
    def __init__(self):self.objects={'archive-index.json':b'{"dates":["2025-01-01"]}'};self.puts=[];self.deletes=[]
    def get(self,name):return self.objects.get(name)
    def put(self,name,data):self.puts.append(name);self.objects[name]=data
    def delete(self,name):self.deletes.append(name);del self.objects[name]


def test_archive_backup_all_before_upload_resume_and_exact_rollback(tmp_path,monkeypatch):
    from pipeline.publication_archive import prepare_archive,apply_archive,rollback_archive
    artifact,_,_=fixture(tmp_path,monkeypatch);storage=Storage();original=deepcopy(storage.objects)
    state=tmp_path/'private-archive'
    plan=prepare_archive(artifact,state,storage)
    # No images: 27 JSON assets + 18 PDFs + ZIP + manifest + index.
    assert storage.puts==[] and len(plan['objects'])==48
    assert all((state/r['after_file']).exists() for r in plan['objects'])
    apply_archive(artifact,state,storage);count=len(storage.puts)
    apply_archive(artifact,state,storage);assert len(storage.puts)==count
    assert 'latest.zip' not in storage.objects
    rollback_archive(state,storage);assert storage.objects==original
    rollback_archive(state,storage);assert storage.objects==original
    with pytest.raises(ValueError,match='rollback'):apply_archive(artifact,state,storage)


def test_archive_failed_upload_does_not_resend_and_foreign_edit_blocks_rollback(tmp_path,monkeypatch):
    from pipeline.publication_archive import apply_archive,rollback_archive
    artifact,_,_=fixture(tmp_path,monkeypatch);storage=Storage();state=tmp_path/'private'
    original_put=storage.put
    def fail(name,data):storage.puts.append(name);raise TimeoutError()
    storage.put=fail
    with pytest.raises(TimeoutError):apply_archive(artifact,state,storage)
    storage.put=original_put
    with pytest.raises(ValueError,match='uncertain'):apply_archive(artifact,state,storage)
    assert len(storage.puts)==1
    journal=json.loads((state/'journal.json').read_bytes())
    name=next(iter(journal['writes']));storage.objects[name]=b'foreign'
    with pytest.raises(ValueError,match='Competing'):rollback_archive(state,storage)
    assert storage.deletes==[]


def test_archive_response_lost_can_resume_if_target_is_read_back(tmp_path,monkeypatch):
    from pipeline.publication_archive import apply_archive
    artifact,_,_=fixture(tmp_path,monkeypatch);storage=Storage();state=tmp_path/'private'
    original_put=storage.put
    def lost(name,data):original_put(name,data);raise TimeoutError()
    storage.put=lost
    with pytest.raises(TimeoutError):apply_archive(artifact,state,storage)
    first=storage.puts[0];storage.put=original_put
    apply_archive(artifact,state,storage)
    assert storage.puts.count(first)==1


def test_archive_tamper_and_auth_failure_do_not_become_missing(tmp_path,monkeypatch):
    import requests
    from pipeline.publication_archive import prepare_archive,apply_archive,ArchiveStorage
    from pipeline.publication_database import PROJECT
    artifact,_,_=fixture(tmp_path,monkeypatch);storage=Storage();state=tmp_path/'private'
    plan=prepare_archive(artifact,state,storage)
    (state/plan['objects'][0]['after_file']).write_bytes(b'tampered')
    with pytest.raises(ValueError,match='hash'):apply_archive(artifact,state,storage)
    assert storage.puts==[]
    response=requests.Response();response.status_code=403
    monkeypatch.setattr(requests,'get',lambda *a,**k:response)
    with pytest.raises(requests.HTTPError):ArchiveStorage(f'https://{PROJECT}.supabase.co','key').get('anything')


def test_publication_orders_pair_archive_then_db_and_verifies(tmp_path,monkeypatch):
    from pipeline.kidsnews_python import finish_publication
    artifact,_,_=fixture(tmp_path,monkeypatch);storage=Storage();state=tmp_path/'private';client=Client()
    events=[]
    @contextmanager
    def lock():yield
    client.publication_lock=lock
    def execute(sql):
        assert (state/'database/rollback.sql').exists() and (state/'archive/prepared.json').exists()
        assert json.loads((state/'archive/journal.json').read_bytes())['verified']
        client.executed.append(sql);events.append('db')
    client.execute=execute;client.verify_database=lambda s:events.append('verify-db')
    monkeypatch.setattr('pipeline.kidsnews_python.verify_website',lambda a:events.append('website'))
    assert finish_publication(artifact,state,client,storage)['status']=='complete'
    assert events.index('db')<events.index('verify-db')
    reads=client.reads;puts=len(storage.puts)
    finish_publication(artifact,state,client,storage)
    assert client.reads==reads and len(client.executed)==1 and len(storage.puts)==puts


def test_publish_acknowledgement_checked_before_any_model_or_write(monkeypatch):
    from pipeline.kidsnews_python import execute
    monkeypatch.setattr('pipeline.kidsnews_python.CursorJSONProvider',lambda *a:pytest.fail('No model'))
    with pytest.raises(ValueError,match='acknowledgement'):execute({'publish':True,'execute':True})
    with pytest.raises(ValueError,match='execute'):execute({'operation':'backfill'})


def test_postgres_tls_and_project_guard():
    from pipeline.publication_postgres import PostgresClient
    from pipeline.publication_database import PROJECT
    with pytest.raises(ValueError,match='TLS'):PostgresClient(f'postgresql://user:pass@db.{PROJECT}.supabase.co/db')
    with pytest.raises(ValueError,match='approved'):PostgresClient('postgresql://user:pass@wrong/db?sslmode=require')
    with pytest.raises(ValueError,match='session'):PostgresClient(f'postgresql://user:pass@db.{PROJECT}.supabase.co:6543/db?sslmode=require')
    assert PostgresClient(f'postgresql://user:pass@db.{PROJECT}.supabase.co/db?sslmode=require').project==PROJECT


def test_editor_rejects_one_body_and_uses_same_five_reserve(tmp_path,monkeypatch):
    from pipeline.kidsnews_api_editor import edit_groups
    prepared(tmp_path,monkeypatch);provider=Provider();original=provider.complete
    # Unique sources aren't guaranteed by the legacy fixture; tag only its first
    # call and matching targeted repair instead, without changing pinned material.
    bad_count=[0]
    def selective(payload,timeout):
        material=json.loads(payload['messages'][1]['content'])
        if material.get('category')=='News' and 'source' in material and bad_count[0]<2:
            bad_count[0]+=1;value=combined_answer();value['corrected_article']['middle_en']['body']='Too short.'
            provider.calls.append(payload)
            return {'choices':[{'message':{'content':json.dumps(value)},'finish_reason':'stop'}]}
        return original(payload,timeout)
    provider.complete=selective
    assert edit_groups(tmp_path,provider,{'model':'fake'})['ok']
    section=runner.read(tmp_path/'editor-state.json')['News']
    assert any(o['status']=='gone' for o in section['outcomes'])
    assert len(section['accepted'])==3
    assert {a['candidate']['id'] for a in section['accepted']}<=set(section['order'])


def test_http_json_provider_is_pluggable_without_cursor(monkeypatch):
    from pipeline.kidsnews_python import agent_provider
    monkeypatch.setenv('MY_AGENT_KEY','private')
    monkeypatch.setattr('pipeline.kidsnews_python.CursorJSONProvider',lambda *a:pytest.fail('No CLI'))
    sent=[]
    def complete(self,payload,timeout):sent.append(payload);return {'choices':[]}
    monkeypatch.setattr('pipeline.ai_providers.transport.OpenAICompatibleProvider.complete',complete)
    provider,identity=agent_provider({'agent_provider':{'type':'http','model':'grok',
        'endpoint':'https://agent.example/chat/completions','key_env':'MY_AGENT_KEY'}})
    provider.complete({'messages':[]},600)
    assert sent[0]['model']=='grok' and sent[0]['response_format']=={'type':'json_object'}
    assert 'private' not in str(identity)


def test_prepare_exit_two_is_answered_by_api_then_resumes_same_directory(tmp_path,monkeypatch):
    from pipeline.kidsnews_python import prepare_api
    provider=Provider()
    request=tmp_path/'tasks/task/request.json';answer=request.with_name('answer.json')
    runner.write(request,{'request_id':'a'*64,'task':{'messages':[{'role':'user','content':'Fix JSON'}]}})
    calls=[]
    def cli(module,*args):
        calls.append(args)
        return (2,{'read':str(request),'write_to':str(answer)}) if len(calls)==1 else (0,{'ok':True})
    monkeypatch.setattr('pipeline.kidsnews_python.run_cli',cli)
    assert prepare_api(tmp_path,'2026-10-03',tmp_path/'registry.json',provider,{'model':'test'})['ok']
    assert calls[0]==calls[1] and runner.read(answer)['request_id']=='a'*64


def test_archive_delete_exact_bucket_and_name(monkeypatch):
    from pipeline.publication_archive import ArchiveStorage
    from pipeline.publication_database import PROJECT
    import requests
    sent=[]
    response=requests.Response();response.status_code=200
    def delete(url,**kw):sent.append((url,kw));return response
    monkeypatch.setattr(requests,'delete',delete)
    ArchiveStorage(f'https://{PROJECT}.supabase.co','key').delete('2026-10-03/article_images/photo.webp')
    assert sent[0][0].endswith('/object/redesign-daily-content')
    assert sent[0][1]['json']=={'prefixes':['2026-10-03/article_images/photo.webp']}


def test_stale_api_resume_requires_fresh_history_and_never_changes_frozen_input(tmp_path,monkeypatch):
    from datetime import datetime,timedelta,timezone
    from zoneinfo import ZoneInfo
    from pipeline.kidsnews_python import refresh_history_api
    from pipeline.kidsnews_api_editor import edit_groups
    prepared(tmp_path,monkeypatch);before=(tmp_path/'input.json').read_bytes()
    runner.write(tmp_path/'metrics.json',{'started_at':(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()})
    provider=Provider();identity={'model':'fake'}
    with pytest.raises(ValueError,match='stale_run'):refresh_history_api(tmp_path,provider,identity)
    history_date=(datetime.now(ZoneInfo('America/New_York')).date()-timedelta(days=1)).isoformat()
    def registry(day,root):
        path=root/'registry.json'
        runner.write(path,{'date':day,'history':[{'category':c,'published_date':history_date,
            'source_title':'Different old event','source_url':'https://old.example/event'} for c in runner.CATS]})
        return path
    monkeypatch.setattr('pipeline.kidsnews_python.registry',registry)
    original=provider.complete
    def complete(payload,timeout):
        material=json.loads(payload['messages'][1]['content'])
        if 'partition every' in payload['messages'][0]['content']:
            ids=[r['id'] for r in material['candidates']]
            value={'clear_ids':ids[1:],'blocked_ids':ids[:1]}
            return {'choices':[{'message':{'content':json.dumps(value)},'finish_reason':'stop'}]}
        return original(payload,timeout)
    provider.complete=complete
    refresh_history_api(tmp_path,provider,identity,True)
    assert (tmp_path/'input.json').read_bytes()==before
    edit_groups(tmp_path,provider,identity)
    blocked=runner.read(tmp_path/'groups/history-refresh.json')['blocked_ids']
    assert not any(a['candidate']['id'] in blocked for section in runner.read(tmp_path/'editor-state.json').values()
                   for a in section['accepted'])


def test_cli_stdout_is_one_json_even_on_error(monkeypatch,capsys):
    from pipeline.kidsnews_python import main
    import io,sys
    monkeypatch.setattr(sys,'argv',['kidsnews_python'])
    monkeypatch.setattr(sys,'stdin',io.StringIO('{"operation":"backfill"}'))
    assert main()==1
    lines=capsys.readouterr().out.strip().splitlines()
    assert len(lines)==1 and json.loads(lines[0])['ok'] is False
def test_postgres_readonly_preflight_permissions():
    from pipeline.publication_postgres import PostgresClient, TABLES
    client = object.__new__(PostgresClient)
    rows = [{'relname': table, 'writable': True, 'owns': True} for table in TABLES]
    client.query = lambda sql: rows
    client.preflight()
    rows[0]['writable'] = False
    import pytest
    with pytest.raises(ValueError, match='permissions'):
        client.preflight()
    rows[0]['writable'] = True
    next(row for row in rows if row['relname'] == 'redesign_search_index')['owns'] = False
    with pytest.raises(ValueError, match='ownership'):
        client.preflight()
