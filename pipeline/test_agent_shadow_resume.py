"""Review B1–B7/S7: offline crash, transport and recovery regressions."""
import hashlib
import json
import sys
import time

import pytest
import requests

from pipeline import agent_shadow as runner
from pipeline import agent_shadow_providers as routing
from pipeline.ai_providers.transport import AgentNeeded, OpenAICompatibleProvider
from pipeline.agent_shadow_batch import validate_batch


def setup(root, monkeypatch, fallback=False):
    root.mkdir(parents=True, exist_ok=True)
    runner.write(root / 'providers.json', {'roles': {'write': {'type': 'http',
        'model': 'test', 'endpoint': 'https://example.invalid/chat', 'key_env': 'TEST_RESUME_KEY'}}})
    runner.write(root / 'input.json', {'http_fallback': 'native' if fallback else None})
    monkeypatch.setenv('TEST_RESUME_KEY', 'offline-only')
    return routing.TaskRouter(root, 'rewrite-News-c001')


PAYLOAD = {'model': 'native-agent', 'messages': []}
RESULT = {'choices': [{'message': {'content': '{"ok":true}'}, 'finish_reason': 'stop'}],
          'usage': {'total_tokens': 12}}


def http_error(status, retry='0'):
    response = requests.Response()
    response.status_code = status
    response.headers['Retry-After'] = retry
    return requests.HTTPError('offline', response=response)


def test_http_4xx_is_retryable_in_same_run(tmp_path, monkeypatch):
    router = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', lambda *a: (_ for _ in ()).throw(http_error(401)))
    with pytest.raises((RuntimeError, ValueError)):
        router.complete(PAYLOAD, 0)
    state = runner.read(next(tmp_path.glob('tasks/*/*/http-attempt.json')))
    assert state['status'] == 'failed_not_executed' and state['http_status'] == 401
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', lambda *a: RESULT)
    assert router.complete(PAYLOAD, 0)['choices'] == RESULT['choices']


def test_read_timeout_is_uncertain_not_retried(tmp_path, monkeypatch):
    router = setup(tmp_path, monkeypatch)
    calls = []
    def fail(*args):
        calls.append(1)
        raise requests.ReadTimeout('offline')
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', fail)
    for _ in range(2):
        with pytest.raises((RuntimeError, ValueError)):
            router.complete(PAYLOAD, 0)
    assert len(calls) == 1
    assert runner.read(next(tmp_path.glob('tasks/*/*/http-attempt.json')))['status'] == 'outcome_uncertain'


def test_429_waits_retry_after_within_budget(tmp_path, monkeypatch):
    router = setup(tmp_path, monkeypatch)
    calls, sleeps = [], []
    def fake(*args):
        calls.append(1)
        if len(calls) == 1:
            raise http_error(429, '500')
        return RESULT
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', fake)
    monkeypatch.setattr(routing.time, 'sleep', sleeps.append)
    router.complete(PAYLOAD, 0)
    assert len(calls) == 2 and sum(sleeps) == 120 and max(sleeps) <= 60


def test_resume_after_saved_answer_before_http_complete(tmp_path, monkeypatch):
    router = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', lambda *a: RESULT)
    router.complete(PAYLOAD, 0)
    path = next(tmp_path.glob('tasks/*/*/http-attempt.json'))
    state = runner.read(path)
    state['status'] = 'attempting'
    runner.write(path, state)
    (tmp_path / 'provider-audit.json').unlink()
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', lambda *a: pytest.fail('duplicate HTTP'))
    router.complete(PAYLOAD, 0)
    answer = runner.read(path.parent / 'answer.json')
    assert {'revision', 'usage', 'attempt_id'} <= answer.keys()
    assert runner.read(tmp_path / 'provider-audit.json')['http_calls'] >= 1


def test_resume_after_wall_deadline_without_resetting_budget(tmp_path, monkeypatch):
    router = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', lambda *a: RESULT)
    router.complete(PAYLOAD, 0)
    audit = runner.read(tmp_path / 'provider-audit.json')
    audit['started_unix'] = time.time() - 3700
    runner.write(tmp_path / 'provider-audit.json', audit)
    routing.TaskRouter(tmp_path, 'rewrite-News-c002').complete(PAYLOAD, 0)
    after = runner.read(tmp_path / 'provider-audit.json')
    assert after['task_count'] == 2 and after['http_calls'] == 2


def test_batch_skipping_top_importance_does_not_consume_batch():
    pool = [{'id': f'c{i}', 'importance': 4 if i == 0 else 2} for i in range(8)]
    value = {'drafts': [{'id': 'c1', 'reason': 'source supports it', 'article': {}}],
             'skipped': [{'id': 'c0', 'reason': 'insufficient evidence'}]}
    assert validate_batch(value, pool, 'News') == []
    value['drafts'].append({'id': 'c0', 'reason': 'included', 'article': {}})
    assert validate_batch(value, pool, 'News')


def test_recovery_cli_single_json_and_exit_codes(tmp_path):
    with pytest.raises(runner.StepFinished) as exc:
        runner.boundary(tmp_path, 'test', True)
    assert exc.value.result['next'].startswith(sys.executable)
    import subprocess
    runner.write(tmp_path / 'input.json', {'date': '2026-09-30', 'candidates': [],
        'history': {c: [] for c in runner.CATS}, 'sources': {}})
    runner.write(tmp_path / 'metrics.json', {'steps': []})
    cmd = [sys.executable, '-m', 'pipeline.agent_shadow', 'step', '--run-dir', str(tmp_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 2 and len(result.stdout.splitlines()) == 1
    handoff = json.loads(result.stdout)
    assert handoff['rerun'].startswith(sys.executable)
    runner.write(__import__('pathlib').Path(handoff['write_to']), {'request_id': handoff['request_id'],
        'content': json.dumps({'catalog': {c: [] for c in runner.CATS}}), 'finish_reason': 'stop'})
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0 and len(result.stdout.splitlines()) == 1
    assert json.loads(result.stdout)['next'].startswith(sys.executable)
    runner.write(tmp_path / 'accepted-answer-hashes.json', {'missing.json': 'abc'})
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 1 and len(result.stdout.splitlines()) == 1


def test_http_failure_falls_back_to_native_once_and_labels_it(tmp_path, monkeypatch):
    router = setup(tmp_path, monkeypatch, True)
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', lambda *a: (_ for _ in ()).throw(requests.ReadTimeout()))
    with pytest.raises(AgentNeeded) as exc:
        router.complete(PAYLOAD, 0)
    needed = exc.value
    runner.write(needed.answer, {'request_id': needed.request_id, 'content': '{}', 'finish_reason': 'stop'})
    assert router.complete(PAYLOAD, 0)['choices'][0]['message']['content'] == '{}'
    audit = runner.read(tmp_path / 'provider-audit.json')
    assert audit['fallback_tasks'] == 1 and audit['task_count'] == 2
    assert next(iter(audit['requests'].values()))['fallback'] == 'native'


def test_fallback_budget_counts_into_max_tasks(tmp_path, monkeypatch):
    router = setup(tmp_path, monkeypatch, True)
    monkeypatch.setattr(routing, 'MAX_TASKS', 1)
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', lambda *a: (_ for _ in ()).throw(requests.ReadTimeout()))
    with pytest.raises(ValueError, match='budget'):
        router.complete(PAYLOAD, 0)


def test_content_errors_never_trigger_fallback(tmp_path, monkeypatch):
    router = setup(tmp_path, monkeypatch, True)
    invalid = {'choices': [{'message': {'content': 'not-json'}, 'finish_reason': 'stop'}]}
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', lambda *a: invalid)
    router.complete(PAYLOAD, 0)
    assert runner.read(tmp_path / 'provider-audit.json').get('fallback_tasks', 0) == 0


def test_two_consecutive_fallback_runs_stop(tmp_path, monkeypatch):
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', lambda *a: (_ for _ in ()).throw(requests.ReadTimeout()))
    with pytest.raises(AgentNeeded):
        setup(tmp_path / 'run1', monkeypatch, True).complete(PAYLOAD, 0)
    with pytest.raises(ValueError, match='consecutive'):
        setup(tmp_path / 'run2', monkeypatch, True).complete(PAYLOAD, 0)


def test_probe_b1_401_same_directory_recovers(tmp_path, monkeypatch):
    test_http_4xx_is_retryable_in_same_run(tmp_path, monkeypatch)


def test_probe_b2_attempting_reuses_saved_answer(tmp_path, monkeypatch):
    test_resume_after_saved_answer_before_http_complete(tmp_path, monkeypatch)


def test_news_without_important_candidate_stops_after_first_batch(tmp_path, monkeypatch):
    from pipeline.test_agent_shadow_batch import setup_batch
    from pipeline.test_agent_shadow_review_fixes import run_steps
    fetched, _, tasks, answer = setup_batch(tmp_path, monkeypatch)
    def low(root, key, system, material, validate, **kw):
        value = answer(root, key, system, material, validate, **kw)
        if key == 'plan':
            for row in value['catalog']['News']:
                row['importance'] = 2
        return value
    monkeypatch.setattr(runner, 'ask', low)
    result = run_steps(tmp_path)
    assert result['counts'] == {'news': 3, 'science': 3, 'fun': 3}
    assert len({k for k in tasks if k.startswith('rewrite-batch-News-')}) == 1
    assert not any(k.startswith('discover-News-') for k in tasks)
    assert sum(v for k, v in fetched.items() if k.startswith('news')) <= 8


def test_probe_b4_low_importance_preserves_other_categories(tmp_path, monkeypatch):
    test_news_without_important_candidate_stops_after_first_batch(tmp_path, monkeypatch)


def test_status_without_lock_returns_answer_integrity(tmp_path, monkeypatch, capsys):
    runner.write(tmp_path / 'input.json', {})
    runner.write(tmp_path / 'accepted-answer-hashes.json', {'missing.json': 'abc'})
    monkeypatch.setattr(sys, 'argv', ['shadow', 'status', '--run-dir', str(tmp_path)])
    with runner.run_lock(tmp_path):
        assert runner.main() == 0
    value = json.loads(capsys.readouterr().out)
    assert value['answer_integrity']['ok'] is False


def test_boundary_logging_failure_is_nonfatal(tmp_path):
    (tmp_path / 'steps.jsonl').mkdir()
    with pytest.raises(runner.StepFinished):
        runner.boundary(tmp_path, 'test', True)


def test_stale_run_requires_confirm_and_fresh_history(tmp_path, monkeypatch):
    runner.write(tmp_path / 'input.json', {'date': '2026-09-30', 'history': {c: [] for c in runner.CATS}})
    runner.write(tmp_path / 'metrics.json', {'started_at': '2026-09-28T00:00:00-04:00'})
    with pytest.raises(ValueError, match='confirm-stale'):
        runner.check_stale(tmp_path, False, None)
    with pytest.raises(ValueError, match='registry'):
        runner.check_stale(tmp_path, True, None)


def test_fetch_audit_survives_crash_after_body_save(tmp_path, monkeypatch):
    from pipeline.test_agent_shadow_batch import setup_batch
    from pipeline.agent_shadow_batch import BatchEditor
    _, _, _, answer = setup_batch(tmp_path, monkeypatch)
    snapshot = runner.read(tmp_path / 'input.json')
    policy = BatchEditor(tmp_path, snapshot, answer, runner.boundary, False)
    policy.plan()
    monkeypatch.setattr(policy, 'save', lambda: (_ for _ in ()).throw(RuntimeError('crash')))
    with pytest.raises(RuntimeError, match='crash'):
        policy.pool('News', 8)
    cache = runner.read(tmp_path / 'bodies.json')
    assert all('_fetch_audit' in a for a in cache.values())
    other = BatchEditor(tmp_path, snapshot, answer, runner.boundary, False)
    assert set(cache) <= other.audit['fetch_results'].keys()


def test_fallback_batch_is_four_no_max_tokens_and_same_request(tmp_path, monkeypatch):
    tmp_path = tmp_path / 'isolated' / 'run'
    setup(tmp_path, monkeypatch, True)
    router = routing.TaskRouter(tmp_path, 'rewrite-batch-News-8')
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', lambda *a: (_ for _ in ()).throw(requests.ReadTimeout()))
    payload = {**PAYLOAD, 'max_tokens': 8192}
    with pytest.raises(AgentNeeded) as exc:
        router.complete(payload, 0)
    req = runner.read(exc.value.request)
    expected = hashlib.sha256(json.dumps(router.prepare_payload(payload), sort_keys=True,
                                         separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    assert req['request_id'] == expected and 'max_tokens' not in req['task']
    assert 'FOUR' in req['instructions']


def test_completed_fallback_pack_labels_manifest_review_and_records(tmp_path, monkeypatch):
    from pipeline.test_agent_shadow_batch import setup_batch
    from pipeline.test_agent_shadow_review_fixes import run_steps
    from pipeline.publication_bundle import build
    _, _, _, answer = setup_batch(tmp_path, monkeypatch)
    from PIL import Image
    from pipeline import agent_shadow_batch as batch
    def real_image(url, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (320, 200), 'blue').save(path, 'WEBP')
        return {'width': 320, 'height': 200}
    monkeypatch.setattr(batch, 'safe_image', real_image)
    runner.write(tmp_path / 'provider-audit.json', {'requests': {
        'rewrite-batch-News-8:test': {'fallback': 'native'}}, 'fallback_tasks': 1})
    run_steps(tmp_path)
    assert runner.read(tmp_path / 'done.json')['provider'] == 'mixed'
    assert runner.read(tmp_path / 'site/shadow-run.json')['provider'] == 'mixed'
    outcomes = runner.read(tmp_path / 'review-results.json')['outcomes']
    assert all(o['review_method'] == '同模型写稿并自检' for o in outcomes if o['category'] == 'News')
    bundle = build(tmp_path, tmp_path / 'archive.zip')
    import zipfile
    with zipfile.ZipFile(bundle['zip']) as z:
        records = json.loads(z.read('publication-records.json'))
    assert all(r['writer_provider'] == 'native' for r in records if r['category'] == 'News')


def test_per_category_exhaustion_stops_refill_without_starving_others(tmp_path, monkeypatch):
    from pipeline.test_agent_shadow_batch import setup_batch
    from pipeline.agent_shadow_batch import BatchEditor
    setup_batch(tmp_path, monkeypatch)
    snapshot = runner.read(tmp_path / 'input.json')
    policy = BatchEditor(tmp_path, snapshot, runner.ask, runner.boundary, False)
    policy.plan()
    policy.audit['exhausted_categories'] = {'News': True}
    assert policy.extend('News', 8, {'accepted': []}) is None
    assert policy.pool('Science', 8)


def test_fallback_content_correction_never_returns_to_http(tmp_path, monkeypatch):
    tmp_path = tmp_path / 'isolated' / 'run'
    setup(tmp_path, monkeypatch, True)
    runner.write(tmp_path / 'metrics.json', {'steps': []})
    calls = []
    def fail(*a):
        calls.append(1)
        raise requests.ReadTimeout()
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', fail)
    def invoke():
        return runner.ask(tmp_path, 'rewrite-News-c001', 'test', {}, lambda v: [] if v.get('ok') else ['ok required'])
    with pytest.raises(AgentNeeded) as first:
        invoke()
    runner.write(first.value.answer, {'request_id': first.value.request_id, 'content': '{}', 'finish_reason': 'stop'})
    with pytest.raises(AgentNeeded) as correction:
        invoke()
    runner.write(correction.value.answer, {'request_id': correction.value.request_id, 'content': '{"ok":true}', 'finish_reason': 'stop'})
    assert invoke() == {'ok': True} and len(calls) == 1


def test_malformed_http_envelope_is_not_native_transport_fallback(tmp_path, monkeypatch):
    tmp_path = tmp_path / 'isolated' / 'run'
    router = setup(tmp_path, monkeypatch, True)
    calls = []
    def invalid(*args):
        calls.append(1)
        return {'choices': []}
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', invalid)
    for _ in range(2):
        with pytest.raises(ValueError, match='response_invalid'):
            router.complete(PAYLOAD, 0)
    assert len(calls) == 1


def test_stale_confirm_rechecks_final_category_and_preserves_budgets(tmp_path, monkeypatch):
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo('America/New_York')).date()
    day = (now - timedelta(days=2)).isoformat()
    runner.write(tmp_path / 'input.json', {'date': day, 'candidates': [{'id': 'a', 'category': 'News'}],
        'history': {c: [] for c in runner.CATS}})
    runner.write(tmp_path / 'metrics.json', {'started_at': '2026-09-01T00:00:00-04:00',
        'body_fetches': 7, 'body_fetches_by_category': {'News': 7, 'Science': 0, 'Fun': 0}})
    runner.write(tmp_path / 'autonomous-catalog.json', {'catalog': {'News': [], 'Science': [], 'Fun': [{'id': 'a'}]}})
    runner.write(tmp_path / 'editor-state.json', {c: {'accepted': [{'candidate': {'id': 'a'}}] if c == 'Fun' else [],
                                                  'outcomes': []} for c in runner.CATS})
    registry = tmp_path / 'fresh.json'
    runner.write(registry, {'date': now.isoformat(), 'history': [{'category': 'Fun',
        'published_date': (now-timedelta(days=1)).isoformat(), 'source_title': 'same event'}]})
    def check(root, key, system, material, validate):
        assert material['candidates'][0]['category'] == 'Fun'
        assert not validate({'blocked_ids': ['a']})
        return {'blocked_ids': ['a']}
    monkeypatch.setattr(runner, 'ask', check)
    runner.check_stale(tmp_path, True, registry)
    assert runner.read(tmp_path / 'input.json')['date'] == day
    assert runner.read(tmp_path / 'metrics.json')['body_fetches'] == 7
    assert runner.read(tmp_path / 'editor-state.json')['Fun']['accepted'] == []


@pytest.mark.parametrize('exc,expected', [
    (requests.ConnectTimeout(), 'failed_not_executed'),
    (requests.ConnectionError('Failed to establish a new connection'), 'failed_not_executed'),
    (requests.ConnectionError('Connection reset by peer'), 'outcome_uncertain'),
    (http_error(503), 'failed_not_executed'),
])
def test_transport_classification_preserves_reset_uncertainty(exc, expected):
    assert routing.transport_failure(exc)['status'] == expected
