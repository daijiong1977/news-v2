"""Malformed HTTP answers and real module-entry exceptions: offline regressions."""
import json
import runpy
import subprocess
import sys
import pytest
from pipeline import agent_shadow as runner
from pipeline.ai_providers.transport import OpenAICompatibleProvider


def test_module_entry_uses_same_rejection_class():
    entry = runpy.run_module('pipeline.agent_shadow', run_name='entry_probe')
    assert entry['AnswerRejected'] is runner.AnswerRejected


@pytest.mark.parametrize('answers,success', [
    (['not json', '{"words":281}', '{"words":330}'], True),
    (['not json', 'still not json'], False),
    (['{"words":281}', '{"words":280}'], False),
])
def test_format_and_content_have_separate_bounded_repairs(tmp_path, monkeypatch, answers, success):
    runner.write(tmp_path / 'input.json', {'test_profile': 'news-deepseek'})
    runner.write(tmp_path / 'metrics.json', {'steps': []})
    runner.write(tmp_path / 'providers.json', {'roles': {'write': {'type': 'http',
        'model': 'test', 'endpoint': 'https://api.example/chat/completions', 'key_env': 'OFFLINE_KEY'}}})
    monkeypatch.setenv('OFFLINE_KEY', 'fake')
    calls = []
    def complete(self, payload, timeout):
        calls.append(payload)
        return {'choices': [{'message': {'content': answers[len(calls)-1]}, 'finish_reason': 'stop'}],
                'usage': {'total_tokens': 10}}
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', complete)
    invoke = lambda: runner.ask(tmp_path, 'rewrite-News-c041', 'JSON only', {},
                               lambda value: [] if value.get('words', 0) >= 300 else ['middle too short'])
    if success:
        assert invoke()['words'] == 330
        assert calls[1]['messages'][-2] == {'role': 'assistant', 'content': 'not json'}
        assert 'format only' in calls[1]['messages'][-1]['content'].lower()
        assert 'middle too short' in calls[2]['messages'][-1]['content']
        audit = runner.read(tmp_path / 'provider-audit.json')
        attempts = next(iter(audit['requests'].values()))['attempts']
        assert len(attempts) == 3 and sum(a['usage']['total_tokens'] for a in attempts) == 30
    else:
        with pytest.raises(runner.AnswerRejected):
            invoke()
    assert len(calls) == len(answers)


def test_real_cli_skips_invalid_cached_rewrite_instead_of_exiting_one(tmp_path, monkeypatch):
    from pipeline.test_agent_shadow_autonomous import setup
    from pipeline.agent_shadow_autonomous import AutonomousEditor
    from pipeline.news_rss_core import TRI_VARIANT_REWRITER_PROMPT, tri_variant_rewriter_input
    setup(tmp_path, monkeypatch)
    snapshot = runner.read(tmp_path / 'input.json')
    snapshot['active_categories'] = ['News']
    # No HTTP or env dependency: exercise the same CLI exception path with cached native answer.
    runner.write(tmp_path / 'input.json', snapshot)
    catalog = {c: [] for c in runner.CATS}
    catalog['News'] = [{'id': 'news00', 'topic': 'politics', 'importance': 4,
        'initial_risk': 0, 'history_status': 'clear', 'history_confidence': 1}]
    runner.write(tmp_path / 'autonomous-catalog.json', {'catalog': catalog,
        'candidates': snapshot['candidates'], 'sources': snapshot['sources']})
    policy = AutonomousEditor(tmp_path, snapshot, None, lambda *a: None, False)
    policy.catalog = catalog
    pool = policy.pool('News', 3)
    runner.write(tmp_path / 'pool-News-3.json', pool)
    art = pool[0]['article']
    import re
    user = re.sub(r'^Today: .*', 'Today: 2026-09-30.', tri_variant_rewriter_input([(0, art)], category='News'))
    from pipeline.ai_providers.transport import AgentFilesProvider, AgentNeeded
    payload = {'model': 'native-agent', 'messages': [
        {'role': 'system', 'content': TRI_VARIANT_REWRITER_PROMPT}, {'role': 'user', 'content': user}]}
    with pytest.raises(AgentNeeded) as pending:
        AgentFilesProvider(tmp_path / 'tasks/rewrite-News-news00').complete(payload, 0)
    needed = pending.value
    runner.write(needed.answer, {'request_id': needed.request_id, 'content': '{}', 'finish_reason': 'stop'})
    runner.write(needed.answer.parent / 'validation-errors.json', [['invalid rewrite']])
    runner.write(tmp_path / 'completed-steps.json', ['plan', 'originals-News-3', 'selections-News-3'])
    runner.write(tmp_path / 'backfill.json', {'targets': {c: 3 for c in runner.CATS}})
    runner.write(tmp_path / 'editor-state.json', {c: {'accepted': [], 'outcomes': [],
        'order': ['news00'] if c == 'News' else [], 'pool_ids': ['news00'] if c == 'News' else [],
        'pick_done': c == 'News'} for c in runner.CATS})
    result = subprocess.run([sys.executable, '-m', 'pipeline.agent_shadow', 'step', '--run-dir', str(tmp_path)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(result.stdout.splitlines()) == 1
    assert json.loads(result.stdout)['completed_step'] == 'rewrite-invalid-News-news00'
    assert runner.read(tmp_path / 'review-results.json')['outcomes'][0]['status'] == 'rewrite_invalid'


@pytest.mark.parametrize('fixed', [True, False])
def test_modifier_corrects_or_replaces_never_calls_third_review(tmp_path, monkeypatch, fixed):
    from pipeline.test_agent_shadow_autonomous import setup
    from pipeline.test_agent_shadow_review_fixes import run_steps, draft
    fetched, _, tasks, answer, _ = setup(tmp_path, monkeypatch)
    snapshot = runner.read(tmp_path / 'input.json')
    snapshot.update(test_profile='news-deepseek', active_categories=['News'])
    runner.write(tmp_path / 'input.json', snapshot)
    called = []
    def respond(root, key, system, material, validate, **kw):
        called.append(key)
        if key == 'plan':
            value = answer(root, key, system, material, lambda v: [], **kw)
            value['catalog']['Science'] = value['catalog']['Fun'] = []
            return value
        if key == 'review-News-news01':
            value = answer(root, key, system, material, validate, **kw)
            value['facts_supported'] = False
            value['notes'] = 'Restore source attribution.'
            return value
        if key.startswith('review-modify-'):
            value = answer(root, 'review-News-news01', system, material, lambda v: [], **kw)
            value.update(corrected_article=draft(), facts_supported=fixed, notes='Attribution fixed')
            assert not validate(value)
            return value
        return answer(root, key, system, material, validate, **kw)
    monkeypatch.setattr(runner, 'ask', respond)
    result = run_steps(tmp_path)
    assert result['counts']['news'] == 3
    assert set(k for k in called if k.startswith('review-modify-')) == {'review-modify-News-news01'}
    outcomes = runner.read(tmp_path / 'review-results.json')['outcomes']
    row = next(o for o in reversed(outcomes) if o['id'] == 'news01')
    assert row['modifier_attempted']
    assert row['status'] == ('accepted' if fixed else 'review_rejected')
    # Top-up opens a bounded batch of three additional bodies, not just one.
    assert sum(fetched.values()) == (3 if fixed else 6)


def test_modifier_invalid_output_still_replaces_article(tmp_path, monkeypatch):
    from pipeline.test_agent_shadow_autonomous import setup
    from pipeline.test_agent_shadow_review_fixes import run_steps
    _, _, _, answer, _ = setup(tmp_path, monkeypatch)
    snapshot = runner.read(tmp_path / 'input.json')
    snapshot.update(test_profile='news-deepseek', active_categories=['News'], review_mode='modifier')
    runner.write(tmp_path / 'input.json', snapshot)
    called = []
    def respond(root, key, system, material, validate, **kw):
        called.append(key)
        if key == 'plan':
            value = answer(root, key, system, material, lambda v: [], **kw)
            value['catalog']['Science'] = value['catalog']['Fun'] = []
            return value
        if key == 'review-modify-News-news01':
            raise runner.AnswerRejected('Still invalid after correction')
        if key.startswith('review-modify-'):
            from pipeline.test_agent_shadow_review_fixes import draft
            value = answer(root, 'review-News-any', system, material, lambda v: [], **kw)
            value['corrected_article'] = draft()
            assert not validate(value)
            return value
        return answer(root, key, system, material, validate, **kw)
    monkeypatch.setattr(runner, 'ask', respond)
    assert run_steps(tmp_path)['counts']['news'] == 3
    assert not any(k.startswith('review-News-') for k in called)
    row = next(o for o in runner.read(tmp_path / 'review-results.json')['outcomes'] if o['id'] == 'news01')
    assert row['status'] == 'review_invalid' and row['modifier_attempted']


def test_modifier_checks_corrected_words_and_language(tmp_path):
    from pipeline.agent_shadow_modifier import modify
    from pipeline.test_agent_shadow_review_fixes import draft
    observed = []
    def answer(root, key, prompt, material, validate):
        corrected = draft()
        corrected['middle_en']['body'] = 'Short 伊拉克 text.'
        value = {'corrected_article': corrected}
        observed.extend(validate(value))
        return value
    modify(tmp_path, 'News', 'x', {'body': 'Source', 'word_count': 500}, draft(), {}, [], [], answer, lambda v: [])
    assert any('outside' in e for e in observed)
    assert any('Chinese text' in e for e in observed)
