"""News-only experiment: no live network, model, database or deployment."""
import pytest
from pipeline import agent_shadow as runner
from pipeline.agent_shadow_providers import task_role, TaskRouter
from pipeline.test_agent_shadow_autonomous import setup
from pipeline.test_agent_shadow_review_fixes import run_steps


def test_details_review_can_be_offloaded_without_offloading_body_review(tmp_path):
    runner.write(tmp_path / 'providers.json', {'roles': {'detail_review': {'type': 'http',
        'model': 'deepseek-chat', 'endpoint': 'https://api.deepseek.com/chat/completions',
        'key_env': 'DEEPSEEK_API_KEY'}, 'review': {'type': 'native'}}})
    assert task_role('review-details-News-c001') == 'detail_review'
    assert TaskRouter(tmp_path, 'review-details-News-c001').choice['type'] == 'http'
    assert TaskRouter(tmp_path, 'review-News-c001').choice['type'] == 'native'


def test_legacy_details_review_still_uses_review_role(tmp_path):
    runner.write(tmp_path / 'providers.json', {'roles': {'review': {'type': 'native'}}})
    assert TaskRouter(tmp_path, 'review-details-News-c001').choice == {'type': 'native'}


def test_news_scope_skips_other_sections_and_visual_tasks(tmp_path, monkeypatch):
    fetched, _, tasks, answer, _ = setup(tmp_path, monkeypatch)
    snapshot = runner.read(tmp_path / 'input.json')
    snapshot.update(test_profile='news-deepseek', active_categories=['News'])
    runner.write(tmp_path / 'input.json', snapshot)
    def scoped(root, key, system, material, validate, **kw):
        if key == 'plan':
            # The real validator must reject accidental re-routing into inactive sections.
            value = answer(root, key, system, material, lambda v: [], **kw)
            assert validate(value)
            value['catalog']['Science'] = []
            value['catalog']['Fun'] = []
            assert not validate(value)
            return value
        return answer(root, key, system, material, validate, **kw)
    monkeypatch.setattr(runner, 'ask', scoped)
    result = run_steps(tmp_path)
    assert result['counts'] == {'news': 3, 'science': 0, 'fun': 0}
    assert sum(fetched.values()) == 3
    assert not any('Science' in t or 'Fun' in t or t.startswith('review-image-') for t in tasks)
    assert result['image_policy'] == 'source_only_mechanical_not_visual_review'


def test_profile_is_frozen_on_resume(tmp_path):
    runner.write(tmp_path / 'input.json', {'date': '2026-09-30', 'editor_mode': 'autonomous',
        'test_profile': 'news-deepseek', 'history': {'News': [1]}})
    with pytest.raises(ValueError, match='profile is frozen'):
        runner.prepare(tmp_path, '2026-09-30', editor_mode='autonomous')


def test_prepare_collects_news_only(tmp_path, monkeypatch):
    from pipeline import db_config, full_round
    from pipeline.test_agent_shadow import source
    registry = tmp_path / 'registry.json'
    runner.write(registry, {'date': '2026-09-30', 'sources': [], 'history': [
        {'category': 'News', 'published_date': '2026-09-29'}]})
    collected = []
    monkeypatch.setattr(db_config, 'load_sources', lambda cat, **kw: collected.append(cat) or [source()])
    monkeypatch.setattr(full_round, 'phase_a_light', lambda cat, sources, **kw: [])
    runner.prepare(tmp_path, '2026-09-30', registry_file=registry,
                   editor_mode='autonomous', test_profile='news-deepseek')
    assert collected == ['News']
    assert runner.read(tmp_path / 'input.json')['history']['Science'] == []


def test_cli_loads_env_on_step_and_forbids_publish(tmp_path, monkeypatch, capsys):
    import os, sys
    env = tmp_path / 'test.env'
    env.write_text('HYBRID_TEST_ONLY=loaded\n')
    runner.write(tmp_path / 'input.json', {'test_profile': 'news-deepseek'})
    monkeypatch.delenv('HYBRID_TEST_ONLY', raising=False)
    monkeypatch.setattr('pipeline.agent_shadow_logs.ship', lambda root: None)
    def advance(root, **kw):
        assert os.environ.get('HYBRID_TEST_ONLY') == 'loaded'
        return {'ok': True}
    monkeypatch.setattr(runner, 'advance', advance)
    monkeypatch.setattr(sys, 'argv', ['shadow', 'step', '--run-dir', str(tmp_path), '--env-file', str(env)])
    assert runner.main() == 0
    monkeypatch.setattr(sys, 'argv', ['shadow', 'publish', '--run-dir', str(tmp_path)])
    assert runner.main() == 1
    assert 'partial publication is forbidden' in capsys.readouterr().out


def test_http_rewrite_records_usage_and_cache(tmp_path, monkeypatch):
    from pipeline.ai_providers.transport import OpenAICompatibleProvider
    runner.write(tmp_path / 'providers.json', {'roles': {'write': {'type': 'http',
        'model': 'deepseek-chat', 'endpoint': 'https://api.deepseek.com/chat/completions',
        'key_env': 'HYBRID_FAKE_KEY'}}})
    runner.write(tmp_path / 'metrics.json', {'steps': []})
    monkeypatch.setenv('HYBRID_FAKE_KEY', 'offline-placeholder')
    calls = []
    def complete(self, payload, timeout):
        calls.append(payload)
        return {'choices': [{'message': {'content': '{"ok":true}'}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', complete)
    for _ in range(2):
        assert runner.ask(tmp_path, 'rewrite-News-c001', 'write', {}, lambda v: []) == {'ok': True}
    assert len(calls) == 1
    audit = runner.read(tmp_path / 'provider-audit.json')
    assert audit['http_calls'] == 1
    assert next(iter(audit['requests'].values()))['usage']['completion_tokens'] == 5


@pytest.mark.parametrize('corrected', [True, False])
def test_http_invalid_answer_corrected_once_without_bot_handoff(tmp_path, monkeypatch, corrected):
    from pipeline.ai_providers.transport import OpenAICompatibleProvider
    runner.write(tmp_path / 'input.json', {'test_profile': 'news-deepseek'})
    runner.write(tmp_path / 'providers.json', {'roles': {'write': {'type': 'http',
        'model': 'deepseek-chat', 'endpoint': 'https://api.deepseek.com/chat/completions',
        'key_env': 'HYBRID_FAKE_KEY'}}})
    runner.write(tmp_path / 'metrics.json', {'steps': []})
    monkeypatch.setenv('HYBRID_FAKE_KEY', 'offline-placeholder')
    calls = []
    def complete(self, payload, timeout):
        calls.append(payload)
        content = '{"ok":true}' if corrected and len(calls) == 2 else '{}'
        return {'choices': [{'message': {'content': content}, 'finish_reason': 'stop'}]}
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', complete)
    invoke = lambda: runner.ask(tmp_path, 'rewrite-News-c001', 'write', {},
                               lambda v: [] if v.get('ok') else ['ok required'])
    if corrected:
        assert invoke()['ok']
    else:
        with pytest.raises(runner.AnswerRejected):
            invoke()
    assert len(calls) == 2
