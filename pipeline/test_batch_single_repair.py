import json
from copy import deepcopy
import pytest
from pipeline import agent_shadow as runner
from pipeline.ai_providers import AgentNeeded
from pipeline.ai_providers.transport import OpenAICompatibleProvider
from pipeline.test_agent_shadow_batch import setup_batch
from pipeline.test_agent_shadow_review_fixes import run_steps, draft


def test_invalid_batch_json_uses_native_syntax_repair_never_second_http(tmp_path, monkeypatch):
    runner.write(tmp_path / 'input.json', {'test_profile': 'batch-deepseek', 'editor_mode': 'autonomous'})
    runner.write(tmp_path / 'metrics.json', {'steps': []})
    runner.write(tmp_path / 'providers.json', {'roles': {'write': {'type': 'http', 'model': 'deepseek-chat',
        'endpoint': 'https://fixture.invalid/completions', 'key_env': 'FIXTURE_KEY'}}})
    monkeypatch.setenv('FIXTURE_KEY', 'fake_not_a_secret')
    calls = []
    def http(self, payload, timeout):
        calls.append(payload)
        return {'choices': [{'message': {'content': '{"drafts": []'}, 'finish_reason': 'stop'}]}
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', http)
    check = lambda value: [] if isinstance(value.get('drafts'), list) else ['missing drafts']
    with pytest.raises(AgentNeeded) as pending:
        runner.ask(tmp_path, 'rewrite-batch-News-8', 'batch', {}, check)
    assert 'review-format-batch-News-8' in str(pending.value.request)
    runner.write(pending.value.answer, {'request_id': pending.value.request_id,
        'content': json.dumps({'drafts': []}), 'finish_reason': 'stop'})
    assert runner.ask(tmp_path, 'rewrite-batch-News-8', 'batch', {}, check) == {'drafts': []}
    assert len(calls) == 1
    assert runner.read(tmp_path / 'provider-audit.json')['http_calls'] == 1


def test_only_bad_draft_repaired_good_four_untouched(tmp_path, monkeypatch):
    _, _, tasks, answer = setup_batch(tmp_path, monkeypatch)
    def bad(root, key, system, material, validate, **kw):
        if key == 'review-repair-draft-News-news04':
            tasks.append(key)
            assert material['article']['easy_en']['headline'] == ''
            value = {'articles': [draft()]}
            assert not validate(value)
            return value
        value = answer(root, key, system, material, validate, **kw)
        if key == 'rewrite-batch-News-8':
            value['drafts'][0]['article']['easy_en']['headline'] = ''
        return value
    monkeypatch.setattr(runner, 'ask', bad)
    result = run_steps(tmp_path)
    assert result['counts']['news'] == 3
    assert {k for k in tasks if k.startswith('review-repair-draft-')} == {'review-repair-draft-News-news04'}
    assert len({k for k in tasks if k.startswith('rewrite-batch-News-')}) == 1
