import json
from types import SimpleNamespace
import pytest
from pipeline.ai_stage_config import StageProviders
from pipeline.kidsnews_api_editor import CachedJSON


def test_each_stage_routes_and_resume_does_not_call(tmp_path):
    calls = []
    def factory(config):
        name = config['agent_provider']['type']
        def complete(payload, timeout):
            calls.append(name)
            return {'choices':[{'finish_reason':'stop','message':{'content':'{"ok":true}'}}]}
        return SimpleNamespace(complete=complete), {'type':name,'model':name}
    stages = {'pickup':'deepseek','batch_write':'claude','selection':'grok','review':'codex',
              'repair':'claude','format_fix':'claude','history_review':'deepseek'}
    router = StageProviders(tmp_path, {'ai_stages':stages}, factory)
    ask = CachedJSON(tmp_path,router,router.identity)
    keys = ['stage:pickup:p','stage:batch_write:w','group-order-News','review-finish-News-c1',
            'review-detail-fix-News-c1','history-refresh-News']
    for _ in range(2):
        for key in keys:
            assert ask(tmp_path,key,'JSON',{},lambda v:[]) == {'ok':True}
    assert calls == ['deepseek','claude','grok','codex','claude','deepseek']
    with pytest.raises(ValueError,match='Frozen'):
        StageProviders(tmp_path, {'ai_stages':{**stages,'review':'grok'}}, factory)


@pytest.mark.parametrize('stages',[{'typo':'codex'},{'review':{'type':'codex','api_key':'secret'}}])
def test_invalid_stage_config_fails_before_factory(tmp_path,stages):
    def factory(config):
        pytest.fail('Must reject invalid configuration before constructing any provider')
    with pytest.raises(ValueError):
        StageProviders(tmp_path,{'ai_stages':stages},factory)


def test_mixed_http_native_actual_preflight(tmp_path,monkeypatch):
    import sys
    from pipeline import agent_shadow as app
    config = tmp_path/'mixed.json'
    roles = {r:{'type':'native'} for r in ('rank','editor','write','review','details','detail_review','discovery','image_review')}
    roles['write'] = {'type':'http','endpoint':'https://api.deepseek.com/chat/completions',
                      'model':'deepseek-flash','key_env':'DEEPSEEK_API_KEY'}
    app.write(config,{'roles':roles})
    monkeypatch.setenv('DEEPSEEK_API_KEY','offline-placeholder')
    monkeypatch.setattr('dotenv.load_dotenv',lambda *a,**k:None)
    monkeypatch.setattr(app,'prepare',lambda *a,**k:{'ok':True})
    monkeypatch.setattr(app,'check_stale',lambda *a,**k:None)
    monkeypatch.setattr('pipeline.agent_shadow_shortlist.build_drafts',lambda *a:{'ok':True})
    monkeypatch.setattr('pipeline.agent_shadow_logs.ship',lambda *a:None)
    monkeypatch.setattr(sys,'argv',['shadow','preflight','--run-dir',str(tmp_path/'run'),
        '--test-profile','source-first-deepseek','--providers-config',str(config)])
    assert app.main() == 0
    assert app.read(tmp_path/'run/providers.json')['roles']['write']['type'] == 'http'
