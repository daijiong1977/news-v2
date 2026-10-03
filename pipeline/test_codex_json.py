import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_codex_stdin_private_env_usage_and_no_tools(monkeypatch):
    from pipeline.codex_json import CodexJSONProvider
    monkeypatch.setenv('SUPABASE_SERVICE_KEY', 'never-pass-this')
    def run(command, **kw):
        assert '--ignore-user-config' in command and '--ephemeral' in command
        assert command[command.index('--sandbox')+1] == 'read-only'
        assert 'never-pass-this' not in str(kw['env'])
        assert not list(Path(kw['cwd']).iterdir())
        assert command[-1] == '-' and 'messages' in kw['input']
        Path(command[command.index('-o')+1]).write_text('{"ok":true}')
        return SimpleNamespace(returncode=0, stdout=json.dumps({'type':'turn.completed','usage':{'input_tokens':42,'output_tokens':3}}))
    monkeypatch.setattr('subprocess.run', run)
    value = CodexJSONProvider(binary='codex').complete({'messages':[{'role':'user','content':'JSON'}]})
    assert json.loads(value['choices'][0]['message']['content']) == {'ok':True}
    assert value['usage']['input_tokens'] == 42


def test_codex_rejects_tool_calls(monkeypatch):
    from pipeline.codex_json import CodexJSONProvider
    def run(command, **kw):
        Path(command[command.index('-o')+1]).write_text('{}')
        return SimpleNamespace(returncode=0,stdout=json.dumps({'type':'item.completed','item':{'type':'command_execution'}}))
    monkeypatch.setattr('subprocess.run',run)
    with pytest.raises(ValueError,match='tool'): CodexJSONProvider(binary='codex').complete({'messages':[{}]})


def test_codex_all_ai_prepare_routes_native_and_preserves_usage(tmp_path, monkeypatch):
    from pipeline import kidsnews_python as app
    from pipeline.agent_shadow import write, read
    provider, identity = app.agent_provider({'agent_provider':{'type':'codex','binary':'codex'}})
    assert identity['type'] == 'codex-cli-json'
    calls=[]
    def invoke(*args):
        calls.append(args)
        if len(calls)>1: return 0, {'ok':True}
        request=tmp_path/'task/request.json'; answer=tmp_path/'task/answer.json'
        write(request,{'request_id':'abc','task':{'messages':[{'role':'system','content':'Rank supplied material'}]}})
        return 2, {'read':str(request),'write_to':str(answer)}
    monkeypatch.setattr(app,'run_cli',invoke)
    provider.complete=lambda *a: {'choices':[{'message':{'content':'{"ranked":[]}'},'finish_reason':'stop'}],'usage':{'input_tokens':10}}
    app.prepare_api(tmp_path,'2026-10-03',tmp_path/'registry.json',provider,identity,all_ai=True)
    assert '--providers-config' in calls[0]
    assert all(r['type']=='native' for r in read(tmp_path/'all-ai-providers.json')['roles'].values())
    assert read(tmp_path/'task/answer.json')['usage']['input_tokens']==10


def test_all_native_preflight_needs_no_deepseek_key(tmp_path, monkeypatch):
    import sys
    from pipeline import agent_shadow as app
    config=tmp_path/'native.json'
    app.write(config,{'roles':{r:{'type':'native'} for r in
        ('rank','editor','write','review','details','detail_review','discovery','image_review')}})
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    monkeypatch.setattr('dotenv.load_dotenv',lambda *a,**k:None)
    monkeypatch.setattr(app,'prepare',lambda *a,**k:{'ok':True})
    monkeypatch.setattr(app,'check_stale',lambda *a,**k:None)
    monkeypatch.setattr('pipeline.agent_shadow_shortlist.build_drafts',lambda *a:{'ok':True})
    monkeypatch.setattr('pipeline.agent_shadow_logs.ship',lambda *a:None)
    monkeypatch.setattr(sys,'argv',['shadow','preflight','--run-dir',str(tmp_path/'run'),
        '--test-profile','source-first-deepseek','--providers-config',str(config)])
    assert app.main()==0


def test_all_ai_cannot_silently_use_another_provider(tmp_path):
    from pipeline.kidsnews_python import prepare_api
    with pytest.raises(ValueError,match='explicit Codex'):
        prepare_api(tmp_path,'2026-10-03',tmp_path/'registry',None,{'type':'http'},all_ai=True)


def test_website_verification_accepts_same_site_clean_url_only(monkeypatch,tmp_path):
    from pipeline import kidsnews_python as app
    manifest={'version':'2026-10-03'}
    monkeypatch.setattr(app,'load_artifact',lambda p:({'zip_sha256':'hash'},manifest,{}, {'admin.html':b'actual admin'}))
    calls=[]
    def get(url,**kw):
        calls.append(url)
        if 'supabase' in url:
            return SimpleNamespace(status_code=200,json=lambda:manifest,raise_for_status=lambda:None)
        if url.endswith('/admin.html'):
            return SimpleNamespace(status_code=308,headers={'Location':'/admin'},content=b'Redirecting...',raise_for_status=lambda:None)
        return SimpleNamespace(status_code=200,headers={},content=b'actual admin',raise_for_status=lambda:None)
    monkeypatch.setattr(app.requests,'get',get)
    assert app.verify_website(tmp_path)['zip_sha256']=='hash'
    assert calls[-1]=='https://kidsnews.21mins.com/admin'


def test_website_verification_rejects_cross_origin_redirect(monkeypatch,tmp_path):
    from pipeline import kidsnews_python as app
    manifest={}
    monkeypatch.setattr(app,'load_artifact',lambda p:({'zip_sha256':'hash'},manifest,{}, {'admin.html':b'admin'}))
    def get(url,**kw):
        if 'supabase' in url: return SimpleNamespace(json=lambda:manifest,raise_for_status=lambda:None)
        return SimpleNamespace(status_code=308,headers={'Location':'https://untrusted.example/admin'},content=b'',raise_for_status=lambda:None)
    monkeypatch.setattr(app.requests,'get',get)
    with pytest.raises(ValueError,match='redirect'): app.verify_website(tmp_path)
