import json
from pathlib import Path
from types import SimpleNamespace
import pytest


def test_deepseek_batch_switch_keeps_rank_native_and_frozen(tmp_path, monkeypatch):
    from pipeline import kidsnews_python as app
    from pipeline.agent_shadow import read
    monkeypatch.setenv('DEEPSEEK_API_KEY','offline-secret')
    monkeypatch.setattr(app,'run_cli',lambda *a:(0,{'ok':True}))
    primary=SimpleNamespace()
    app.prepare_api(tmp_path,'2026-10-03',tmp_path/'registry',primary,
                    {'type':'codex-cli-json','model':'gpt-6.1-sol'},True,'deepseek')
    roles=read(tmp_path/'all-ai-providers.json')['roles']
    assert roles['write']['type']=='http' and roles['write']['model']=='deepseek-flash'
    assert roles['rank']['type']=='native'
    assert 'offline-secret' not in json.dumps(read(tmp_path/'batch-writer.json'))
    with pytest.raises(ValueError,match='Frozen batch writer'):
        app.prepare_api(tmp_path,'2026-10-03',tmp_path/'registry',primary,
                        {'type':'codex-cli-json','model':'gpt-6.1-sol'},True,'codex')


@pytest.mark.parametrize('selected',['grok','codex','claude'])
def test_native_batch_switch_does_not_change_rank(tmp_path,monkeypatch,selected):
    from pipeline import kidsnews_python as app
    from pipeline.agent_shadow import read,write
    calls=[]
    class Model:
        def __init__(self,name):self.name=name
        def complete(self,payload,timeout):
            calls.append(self.name)
            return {'choices':[{'finish_reason':'stop','message':{'content':'{"drafts":[]}'}}]}
    monkeypatch.setattr(app,'agent_provider',lambda cfg:(Model(selected),{'type':selected,'model':selected}))
    request=tmp_path/'tasks/rewrite-batch-News-8/rid/request.json'
    answer=request.with_name('answer.json')
    write(request,{'request_id':'rid','task':{'messages':[{'role':'user','content':'write'}]}})
    count=[]
    def cli(*args):
        count.append(1)
        return (2,{'read':str(request),'write_to':str(answer)}) if len(count)==1 else (0,{'ok':True})
    monkeypatch.setattr(app,'run_cli',cli)
    app.prepare_api(tmp_path,'2026-10-03',tmp_path/'registry',Model('primary'),
                    {'type':'codex-cli-json','model':'primary'},True,selected)
    assert calls == [selected]
    assert read(answer)['writer_provider']==selected
    assert read(tmp_path/'api-editor-provider.json')['model']=='primary'


def test_claude_no_tools_no_business_secrets(monkeypatch):
    from pipeline.claude_json import ClaudeJSONProvider
    monkeypatch.setenv('SUPABASE_SERVICE_KEY','must-not-pass')
    def run(cmd,**kw):
        assert cmd[cmd.index('--tools')+1]=='' and '--strict-mcp-config' in cmd
        assert '--no-session-persistence' in cmd and '--disable-slash-commands' in cmd
        assert 'must-not-pass' not in str(kw['env'])
        assert not list(Path(kw['cwd']).iterdir())
        return SimpleNamespace(returncode=0,stdout=json.dumps({'type':'result','subtype':'success','result':'{"ok":true}','usage':{'input_tokens':5}}))
    monkeypatch.setattr('subprocess.run',run)
    result=ClaudeJSONProvider(binary='claude').complete({'messages':[{'role':'user','content':'test'}]})
    assert json.loads(result['choices'][0]['message']['content'])=={'ok':True}


def test_claude_incomplete_answer_rejected(monkeypatch):
    from pipeline.claude_json import ClaudeJSONProvider
    monkeypatch.setattr('subprocess.run',lambda *a,**kw:SimpleNamespace(returncode=0,stdout='{"is_error":true}'))
    with pytest.raises(ValueError,match='incomplete'):
        ClaudeJSONProvider(binary='claude').complete({'messages':[{}]})
