"""2026-10-01 Grok follow-up: offline failure-first recovery probes."""
import hashlib
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
import requests

from pipeline import agent_shadow as runner
from pipeline import agent_shadow_providers as routing
from pipeline.agent_shadow_autonomous import AutonomousEditor
from pipeline.agent_shadow_batch import BatchEditor
from pipeline.agent_shadow_lengths import original_band
from pipeline.ai_providers.transport import AgentNeeded, OpenAICompatibleProvider
from pipeline.test_agent_shadow_resume import PAYLOAD, RESULT, setup


@pytest.mark.parametrize('status', ['fallback_native', 'fallback_pending'])
def test_fallback_crash_never_relabels_old_http_answer(tmp_path, monkeypatch, status):
    tmp_path = tmp_path / 'isolated' / 'run'
    router = setup(tmp_path, monkeypatch, True)
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', lambda *a: RESULT)
    router.complete(PAYLOAD, 0)
    directory = next(tmp_path.glob('tasks/*/*/answer.json')).parent
    errors = [['invalid old answer']]
    runner.write(directory / 'validation-errors.json', errors)
    revision = hashlib.sha256(json.dumps(errors, sort_keys=True).encode()).hexdigest()
    state = runner.read(directory / 'http-attempt.json')
    state.update(status=status, revision=revision, original_failure={'status': 'outcome_uncertain'})
    runner.write(directory / 'http-attempt.json', state)
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', lambda *a: pytest.fail('duplicate HTTP'))
    with pytest.raises(AgentNeeded) as exc:
        router.complete(PAYLOAD, 0)
    assert not exc.value.answer.exists()
    assert runner.read(directory / 'answer.before-fallback.json')['content'] == RESULT['choices'][0]['message']['content']
    runner.write(exc.value.answer, {'request_id': exc.value.request_id, 'content': '{"fixed":true}', 'finish_reason': 'stop'})
    assert router.complete(PAYLOAD, 0)['choices'][0]['message']['content'] == '{"fixed":true}'
    answer = runner.read(exc.value.answer)
    assert answer['fallback'] == 'native' and answer['revision'] == revision
    audit = runner.read(tmp_path / 'provider-audit.json')
    assert audit['http_calls'] == 1 and audit['fallback_tasks'] == 1


def test_fallback_interrupt_during_quarantine_resumes_same_request(tmp_path, monkeypatch):
    tmp_path = tmp_path / 'isolated' / 'run'
    router = setup(tmp_path, monkeypatch, True)
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', lambda *a: RESULT)
    router.complete(PAYLOAD, 0)
    directory = next(tmp_path.glob('tasks/*/*/answer.json')).parent
    runner.write(directory / 'validation-errors.json', [['fix']])
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', lambda *a: (_ for _ in ()).throw(requests.ReadTimeout()))
    atomic = routing._atomic_json
    def crash(path, value):
        if path.name == 'answer.before-fallback.json':
            raise OSError('injected disk interruption')
        return atomic(path, value)
    monkeypatch.setattr(routing, '_atomic_json', crash)
    with pytest.raises(OSError, match='injected'):
        router.complete(PAYLOAD, 0)
    assert runner.read(directory / 'http-attempt.json')['status'] == 'fallback_pending'
    monkeypatch.setattr(routing, '_atomic_json', atomic)
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', lambda *a: pytest.fail('duplicate HTTP'))
    with pytest.raises(AgentNeeded) as exc:
        router.complete(PAYLOAD, 0)
    assert exc.value.request_id == directory.name and not exc.value.answer.exists()
    assert runner.read(tmp_path / 'provider-audit.json')['http_calls'] == 2


def test_native_batch_five_rejected_four_accepted_same_id(tmp_path, monkeypatch):
    tmp_path = tmp_path / 'isolated' / 'run'
    setup(tmp_path, monkeypatch, True)
    runner.write(tmp_path / 'metrics.json', {'steps': []})
    runner.write(tmp_path / 'input.json', {'http_fallback': 'native', 'editor_mode': 'autonomous', 'test_profile': 'batch-deepseek'})
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', lambda *a: (_ for _ in ()).throw(requests.ReadTimeout()))
    key = 'rewrite-batch-News-8'
    def ask():
        return runner.ask(tmp_path, key, 'Normally select five drafts.', {'candidates': list(range(8))}, lambda v: [])
    with pytest.raises(AgentNeeded) as first:
        ask()
    needed = first.value
    request = runner.read(needed.request)
    assert 'max_tokens' not in request['task']
    assert any('FOUR' in m['content'] for m in request['task']['messages'])
    def answer(n):
        runner.write(needed.answer, {'request_id': needed.request_id, 'content': json.dumps({'drafts': [{'id': str(i)} for i in range(n)]}), 'finish_reason': 'stop'})
    answer(5)
    with pytest.raises(AgentNeeded) as correction:
        ask()
    assert correction.value.request_id == needed.request_id
    assert any('four' in error.lower() for error in correction.value.errors)
    answer(4)
    assert len(ask()['drafts']) == 4
    assert runner.read(tmp_path / 'provider-audit.json')['http_calls'] == 1


def test_stale_recheck_includes_discovered_ids_and_archive_schema(tmp_path, monkeypatch):
    now = datetime.now(ZoneInfo('America/New_York')).date()
    frozen = (now - timedelta(days=2)).isoformat()
    initial = {'id': 'c1', 'category': 'News'}
    discovered = {'id': 'd1', 'category': 'News'}
    runner.write(tmp_path / 'input.json', {'date': frozen, 'candidates': [initial], 'sources': {}})
    runner.write(tmp_path / 'metrics.json', {'started_at': '2026-01-01T00:00:00-05:00', 'body_fetches': 9})
    runner.write(tmp_path / 'autonomous-catalog.json', {'catalog': {'News': [], 'Science': [], 'Fun': [{'id': 'd1'}]},
        'candidates': [initial, discovered], 'sources': {'discovered:test': {'name': 'test'}}})
    runner.write(tmp_path / 'editor-state.json', {c: {'accepted': [{'candidate': discovered}] if c == 'Fun' else [], 'outcomes': []} for c in runner.CATS})
    history_day = (now - timedelta(days=1)).isoformat()
    rows = [{'id': 'live', 'category': 'Fun', 'published_date': history_day},
            {'id': 'archived', 'category': 'Fun', 'published_date': history_day, 'archived': True},
            {'id': 'legacy-archived', 'category': 'Fun', 'published_date': history_day, 'is_archived': True},
            {'id': 'overwritten', 'category': 'Fun', 'published_date': frozen}]
    registry = tmp_path / 'fresh.json'
    runner.write(registry, {'date': now.isoformat(), 'history': rows})
    def check(root, key, system, material, validate):
        assert {b['id'] for b in material['candidates']} == {'c1', 'd1'}
        assert next(b for b in material['candidates'] if b['id'] == 'd1')['category'] == 'Fun'
        assert [r['id'] for r in material['history']['Fun']] == ['live']
        assert not validate({'blocked_ids': ['d1']})
        return {'blocked_ids': ['d1']}
    monkeypatch.setattr(runner, 'ask', check)
    runner.check_stale(tmp_path, True, registry)
    state = runner.read(tmp_path / 'editor-state.json')
    assert not state['Fun']['accepted']
    assert state['Fun']['outcomes'][-1]['id'] == 'd1'
    assert runner.read(tmp_path / 'input.json')['date'] == frozen
    assert runner.read(tmp_path / 'metrics.json')['body_fetches'] == 9
    assert not runner.read(tmp_path / 'autonomous-catalog.json')['catalog']['Fun']


def cached_editor(root, kind=AutonomousEditor):
    lo, _ = original_band('News')
    candidates = [{'id': sid, 'category': 'News', 'title': sid, 'source': 'S', 'link': 'https://example.org/' + sid} for sid in ('missing', 'cached')]
    runner.write(root / 'bodies.json', {'cached': {**candidates[1], 'body': 'fact ' * lo, 'word_count': lo, 'skip_reason': None}})
    runner.write(root / 'metrics.json', {'body_fetches': 12, 'body_fetches_by_category': {'News': 12, 'Science': 0, 'Fun': 0}})
    editor = kind(root, {'candidates': candidates, 'sources': {}, 'history': {'News': []}}, None, None, False)
    editor.catalog = {'News': [{'id': b['id'], 'topic': 'us_politics', 'importance': 3, 'initial_risk': 0, 'history_status': 'clear', 'history_confidence': 1} for b in candidates]}
    editor.save = lambda: None
    return editor


def test_fetch_cap_skips_uncached_but_keeps_later_cached_original(tmp_path, monkeypatch):
    from pipeline import agent_shadow_autonomous as autonomous
    monkeypatch.setattr(autonomous, 'fetch_original', lambda *a: pytest.fail('fetch past cap'))
    editor = cached_editor(tmp_path)
    assert [b['id'] for b in editor.pool('News', 2)] == ['cached']
    assert runner.read(tmp_path / 'metrics.json')['body_fetches'] == 12
    assert editor.audit['exhausted_categories']['News']


def test_batch_refill_uses_unconsumed_cached_original_at_cap(tmp_path):
    editor = cached_editor(tmp_path, BatchEditor)
    editor.audit['exhausted_categories'] = {'News': True}
    assert editor.extend('News', 8, {}) == 16
    runner.write(tmp_path / 'batch-News-8.json', {'considered': ['cached']})
    assert editor.extend('News', 16, {}) is None


def test_staged_autonomous_extends_to_cached_original_at_cap(tmp_path):
    editor = cached_editor(tmp_path)
    editor.audit['exhausted_categories'] = {'News': True}
    assert editor.extend('News', 1, {}) == 2
