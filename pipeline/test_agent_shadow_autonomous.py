"""Opt-in autonomous editor: offline fakes only, never live AI/search/deployment."""
from dataclasses import asdict
import pytest
from pipeline import agent_shadow as runner
from pipeline.test_agent_shadow_review_fixes import fixture_round, run_steps


def setup(root, monkeypatch):
    fetched, picks, previous = fixture_round(root, monkeypatch)
    snapshot = runner.read(root / 'input.json')
    snapshot['editor_mode'] = 'autonomous'
    runner.write(root / 'input.json', snapshot)
    tasks = []
    def answer(root, key, system, material, validate, **kw):
        tasks.append(key)
        if key == 'plan':
            catalog = {c: [{'id': f'{c.lower()}{i:02d}', 'topic': f'topic{i}',
                'importance': 4 if i == 0 else 1, 'initial_risk': 0,
                'history_status': 'clear', 'history_confidence': 1} for i in range(6)] for c in runner.CATS}
            catalog['Science'][2]['id'] = 'science12'
            value = {'catalog': catalog}
        elif key.startswith('discover-'):
            cat = material['category']
            value = {'articles': [{'url': f'https://public.example/{cat.lower()}/fresh',
                'title': 'Fresh discovery', 'topic': 'new_topic', 'importance': 4,
                'initial_risk': 0, 'history_status': 'clear', 'history_confidence': 1}],
                'reason': 'Existing candidates exhausted'}
        elif key.startswith('review-') and not key.startswith('review-details'):
            from pipeline.news_rss_core import SAFETY_DIMS
            value = {'scores': {'0': {d: 0 for d in SAFETY_DIMS}},
                     'facts_supported': True, 'event_clear': True}
        else:
            return previous(root, key, system, material, validate, **kw)
        assert not validate(value), (key, validate(value))
        return value
    monkeypatch.setattr(runner, 'ask', answer)
    from pipeline import agent_shadow_autonomous as autonomous
    def original(candidate):
        fetched[candidate['id']] += 1
        return {**candidate, 'body': 'fact ' * 400, 'word_count': 400,
                'skip_reason': None, 'og_image': None}
    monkeypatch.setattr(autonomous, 'fetch_original', original)
    monkeypatch.setattr(autonomous, 'validate_public_url', lambda url: url)
    return fetched, picks, tasks, answer, original


def test_direct_three_skips_rank_and_pick_and_fetches_only_nine(tmp_path, monkeypatch):
    fetched, picks, tasks, _, _ = setup(tmp_path, monkeypatch)
    result = run_steps(tmp_path)
    assert result['counts'] == {'news': 3, 'science': 3, 'fun': 3}
    assert sum(fetched.values()) == 9 and all(n == 1 for n in fetched.values())
    assert not picks and 'rank' not in tasks
    assert not any(t.startswith(('pick-', 'discover-')) for t in tasks)
    assert {a['candidate']['id'] for a in runner.read(tmp_path / 'editor-state.json')['Science']['accepted']} == {'science00', 'science01', 'science12'}


def test_rejected_story_only_replaces_that_section_and_keeps_accepted(tmp_path, monkeypatch):
    fetched, _, tasks, answer, _ = setup(tmp_path, monkeypatch)
    def reject(root, key, system, material, validate, **kw):
        if key == 'review-Fun-fun02':
            from pipeline.news_rss_core import SAFETY_DIMS
            return {'scores': {'0': {d: 0 for d in SAFETY_DIMS}}, 'facts_supported': True, 'event_clear': False}
        return answer(root, key, system, material, validate, **kw)
    monkeypatch.setattr(runner, 'ask', reject)
    result = run_steps(tmp_path)
    assert result['counts']['fun'] == 3
    assert sum(n for k, n in fetched.items() if k.startswith('news')) == 3
    # Stepwise resumes revisit a cached rewrite before review, never after acceptance.
    assert tasks.count('rewrite-Fun-fun00') == 2
    assert not any(t.startswith('pick-') for t in tasks)
    assert any(o['id'] == 'fun02' and o['status'] == 'review_rejected'
               for o in runner.read(tmp_path / 'review-results.json')['outcomes'])


def test_discovery_only_for_exhausted_fun_and_temporary_source(tmp_path, monkeypatch):
    fetched, _, tasks, _, original = setup(tmp_path, monkeypatch)
    from pipeline import agent_shadow_autonomous as autonomous
    def bad(candidate):
        result = original(candidate)
        if candidate['id'].startswith('fun'):
            result['skip_reason'] = 'fetch failed'
        return result
    monkeypatch.setattr(autonomous, 'fetch_original', bad)
    result = run_steps(tmp_path)
    assert result['counts']['fun'] == 1
    assert sum(n for k, n in fetched.items() if k.startswith('news')) == 3
    assert {t.split('-')[1] for t in tasks if t.startswith('discover-')} == {'Fun'}
    assert len([t for t in tasks if t.startswith('discover-')]) == 2
    report = runner.read(tmp_path / 'source-suggestions.json')
    assert len(report) == 1 and report[0]['status'] == 'temporary_not_enabled'


@pytest.mark.parametrize('url', ['http://example.com/a', 'https://127.0.0.1/a',
    'https://user:pass@example.com/a', 'https://example.com:8443/a', 'https://[::1]/a'])
def test_discovery_rejects_unsafe_urls_before_fetch(url):
    from pipeline.agent_shadow_autonomous import validate_public_url
    with pytest.raises(ValueError):
        validate_public_url(url)


def test_discovery_cannot_skip_history_or_claim_publisher(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    from pipeline.agent_shadow_autonomous import AutonomousEditor
    policy = AutonomousEditor(tmp_path, runner.read(tmp_path / 'input.json'), runner.ask, runner.boundary, False)
    assert policy.validate_discovery({'articles': [{'url': 'https://public.example/x',
        'title': 'story', 'topic': 'swimming', 'importance': 4, 'initial_risk': 0,
        'history_status': 'clear', 'history_confidence': 1, 'publisher': 'BBC'}]}, 'Fun')


def test_budget_stops_before_additional_fetch(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    from pipeline.agent_shadow_autonomous import AutonomousEditor
    metrics = runner.read(tmp_path / 'metrics.json')
    metrics['body_fetches'] = 36
    runner.write(tmp_path / 'metrics.json', metrics)
    snapshot = runner.read(tmp_path / 'input.json')
    policy = AutonomousEditor(tmp_path, snapshot, runner.ask, runner.boundary, False)
    policy.plan()
    assert policy.pool('News', 3) == []
    assert runner.read(tmp_path / 'autonomous-audit.json')['budget_exhausted']


def test_router_native_discovery_permission_is_narrow_and_budgeted(tmp_path):
    from pipeline.agent_shadow_providers import TaskRouter
    from pipeline.ai_providers import AgentNeeded
    router = TaskRouter(tmp_path, 'discover-Fun-1')
    payload = {'model': 'native-agent', 'messages': [{'role': 'system', 'content': 'discover'}]}
    with pytest.raises(AgentNeeded) as signal:
        router.complete(payload, 0)
    request = runner.read(signal.value.request)
    assert 'search' in request['instructions'].lower()
    with pytest.raises(AgentNeeded):
        router.complete(payload, 0)
    assert runner.read(tmp_path / 'provider-audit.json')['task_count'] == 1
    other = TaskRouter(tmp_path, 'rewrite-Fun-c001')
    with pytest.raises(AgentNeeded) as signal:
        other.complete(payload, 0)
    assert 'Use only the supplied material' in runner.read(signal.value.request)['instructions']


def test_router_http_is_injectable_cached_and_keeps_secrets_out(tmp_path, monkeypatch):
    from pipeline.agent_shadow_providers import TaskRouter
    from pipeline.ai_providers.transport import OpenAICompatibleProvider
    runner.write(tmp_path / 'providers.json', {'roles': {'write': {'type': 'http',
        'model': 'deepseek-chat', 'endpoint': 'https://api.example/chat/completions', 'key_env': 'SHADOW_TEST_KEY'}}})
    monkeypatch.setenv('SHADOW_TEST_KEY', 'not-a-real-secret')
    calls = []
    def fake(self, payload, timeout):
        calls.append(payload)
        assert self.api_key == 'not-a-real-secret'
        return {'choices': [{'message': {'content': '{"ok":true}'}, 'finish_reason': 'stop'}],
                'usage': {'total_tokens': 20}}
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', fake)
    payload = {'model': 'native-agent', 'messages': [{'role': 'system', 'content': 'rewrite'}]}
    router = TaskRouter(tmp_path, 'rewrite-News-c001')
    assert router.complete(payload, 0) == router.complete(payload, 0)
    assert len(calls) == 1 and calls[0]['model'] == 'deepseek-chat'
    assert 'not-a-real-secret' not in ''.join(p.read_text() for p in tmp_path.rglob('*.json'))


def test_router_search_cannot_be_sent_to_text_only_http(tmp_path):
    from pipeline.agent_shadow_providers import TaskRouter
    runner.write(tmp_path / 'providers.json', {'roles': {'discovery': {'type': 'http', 'model': 'x',
        'endpoint': 'https://api.example/chat/completions', 'key_env': 'ANY'}}})
    with pytest.raises(ValueError, match='native'):
        TaskRouter(tmp_path, 'discover-Fun-1').complete({'model': 'native-agent', 'messages': []}, 0)


def test_important_news_reserve_is_sought_even_after_three_light_stories(tmp_path, monkeypatch):
    _, _, _, answer, _ = setup(tmp_path, monkeypatch)
    def plan(root, key, system, material, validate, **kw):
        value = answer(root, key, system, material, validate, **kw)
        if key == 'plan':
            for i, score in enumerate(value['catalog']['News']):
                score['importance'] = 4 if i == 3 else 1
        return value
    monkeypatch.setattr(runner, 'ask', plan)
    result = run_steps(tmp_path)
    assert result['counts']['news'] == 3
    accepted = runner.read(tmp_path / 'editor-state.json')['News']['accepted']
    assert any(a['candidate']['id'] == 'news03' for a in accepted)
    final = [runner.read(p) for p in (tmp_path / 'reader/article_payloads').glob('payload_*-news-*/easy.json')]
    assert any(a['source_url'].endswith('/news03') for a in final)
    assert not any('no qualified high-importance' in w for w in result['warnings'])


def test_final_url_derives_discovered_publisher_not_initial_host(tmp_path, monkeypatch):
    _, _, _, _, original = setup(tmp_path, monkeypatch)
    from pipeline import agent_shadow_autonomous as autonomous
    def redirect(candidate):
        return {**original(candidate), 'evidence_url': 'https://nasa.gov/verified-story'}
    monkeypatch.setattr(autonomous, 'fetch_original', redirect)
    policy = autonomous.AutonomousEditor(tmp_path, runner.read(tmp_path / 'input.json'), runner.ask, runner.boundary, False)
    policy.plan()
    pool = policy.pool('Science', 3)
    assert {policy.snapshot['sources'][b['article']['source']]['rss_url'] for b in pool} == {'https://nasa.gov/'}


def test_safe_image_uses_bounded_fetch_and_has_webp(tmp_path, monkeypatch):
    from io import BytesIO
    from PIL import Image
    from pipeline import agent_shadow_autonomous as autonomous
    buffer = BytesIO()
    Image.new('RGB', (100, 80), 'blue').save(buffer, 'PNG')
    monkeypatch.setattr(autonomous, 'fetch_bytes', lambda *a: (buffer.getvalue(), 'https://public.example/image.png', 'utf-8'))
    target = tmp_path / 'image.webp'
    result = autonomous.safe_image('https://public.example/image.png', target)
    assert result['width'] == 100 and target.is_file()
    with Image.open(target) as img:
        assert img.format == 'WEBP' and img.size == (100, 80)


def test_router_correction_once_and_unknown_http_outcome_not_retried(tmp_path, monkeypatch):
    from pipeline.agent_shadow_providers import TaskRouter
    from pipeline.ai_providers.transport import OpenAICompatibleProvider
    runner.write(tmp_path / 'providers.json', {'roles': {'editor': {'type': 'http',
        'model': 'test', 'endpoint': 'https://api.example/chat/completions', 'key_env': 'SHADOW_TEST_KEY'}}})
    monkeypatch.setenv('SHADOW_TEST_KEY', 'fake')
    calls = []
    def fail(self, payload, timeout):
        calls.append(1)
        raise TimeoutError('unknown delivery')
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', fail)
    router = TaskRouter(tmp_path, 'plan')
    with pytest.raises(RuntimeError, match='do not blindly retry'):
        router.complete({'model': 'test', 'messages': []}, 0)
    with pytest.raises(ValueError, match='uncertain'):
        router.complete({'model': 'test', 'messages': []}, 0)
    assert len(calls) == 1


def test_discovery_can_reuse_unselected_feed_metadata_without_new_sources(tmp_path, monkeypatch):
    _, _, tasks, answer, original = setup(tmp_path, monkeypatch)
    from pipeline import agent_shadow_autonomous as autonomous
    def bad(candidate):
        result = original(candidate)
        if candidate['id'] in {f'fun{i:02d}' for i in range(6)}:
            result['skip_reason'] = 'thin'
        return result
    monkeypatch.setattr(autonomous, 'fetch_original', bad)
    def discover(root, key, system, material, validate, **kw):
        if key.startswith('discover-Fun'):
            tasks.append(key)
            assert any(b['id'] == 'fun06' for b in material['unused_metadata'])
            value = {'articles': [], 'existing': [{'id': f'fun{i:02d}', 'topic': f'topic{i}',
                'importance': 1, 'initial_risk': 0, 'history_status': 'clear', 'history_confidence': 1} for i in range(6, 9)]}
            assert not validate(value)
            return value
        return answer(root, key, system, material, validate, **kw)
    monkeypatch.setattr(runner, 'ask', discover)
    result = run_steps(tmp_path)
    assert result['counts']['fun'] == 3
    assert not (tmp_path / 'source-suggestions.json').exists()


def test_native_discovery_real_handoff_and_completed_answer_hash(tmp_path, monkeypatch):
    from pipeline.ai_providers import AgentNeeded
    runner.write(tmp_path / 'input.json', {'editor_mode': 'autonomous'})
    runner.write(tmp_path / 'metrics.json', {'steps': []})
    with pytest.raises(AgentNeeded) as signal:
        runner.ask(tmp_path, 'discover-Fun-1', 'discover public URLs', {}, lambda v: [])
    runner.write(signal.value.answer, {'request_id': signal.value.request_id,
        'content': '{"articles":[]}', 'finish_reason': 'stop'})
    assert runner.ask(tmp_path, 'discover-Fun-1', 'discover public URLs', {}, lambda v: []) == {'articles': []}
    runner.write(signal.value.answer, {'request_id': signal.value.request_id,
        'content': '{"articles":[],"changed":true}', 'finish_reason': 'stop'})
    with pytest.raises(RuntimeError, match='changed'):
        runner.ask(tmp_path, 'discover-Fun-1', 'discover public URLs', {}, lambda v: [])


def test_fetch_pins_public_ip_checks_tls_and_blocks_private_redirect(monkeypatch):
    from types import SimpleNamespace
    from pipeline import agent_shadow_autonomous as autonomous
    calls = []
    def resolve(host, *a, **kw):
        ip = '127.0.0.1' if host == 'private.test' else '93.184.216.34'
        return [(2, 1, 6, '', (ip, 443))]
    monkeypatch.setattr(autonomous.socket, 'getaddrinfo', resolve)
    class Response:
        raw = SimpleNamespace(_connection=SimpleNamespace(sock=SimpleNamespace(getpeername=lambda: ('93.184.216.34', 443))))
        is_redirect = True
        headers = {'Location': 'https://private.test/secret'}
        def __enter__(self): return self
        def __exit__(self, *a): pass
    class Session:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def mount(self, prefix, adapter):
            assert adapter.poolmanager.connection_pool_kw['assert_hostname'] == 'public.test'
            assert adapter.poolmanager.connection_pool_kw['server_hostname'] == 'public.test'
        def get(self, url, **kw):
            calls.append(url)
            assert kw['headers']['Host'] == 'public.test'
            assert not kw['allow_redirects'] and not self.trust_env
            return Response()
    monkeypatch.setattr(autonomous.requests, 'Session', Session)
    with pytest.raises(ValueError, match='Private'):
        autonomous.fetch_bytes('https://public.test/article', ('text/html',))
    assert calls == ['https://93.184.216.34/article']


def test_http_answer_correction_uses_same_request_and_only_one_extra_call(tmp_path, monkeypatch):
    from pipeline.ai_providers import AgentNeeded
    from pipeline.ai_providers.transport import OpenAICompatibleProvider
    runner.write(tmp_path / 'input.json', {'editor_mode': 'autonomous'})
    runner.write(tmp_path / 'metrics.json', {'steps': []})
    runner.write(tmp_path / 'providers.json', {'roles': {'editor': {'type': 'http',
        'model': 'test', 'endpoint': 'https://api.example/chat/completions', 'key_env': 'SHADOW_TEST_KEY'}}})
    monkeypatch.setenv('SHADOW_TEST_KEY', 'fake')
    calls = []
    def fake(self, payload, timeout):
        calls.append(payload)
        return {'choices': [{'message': {'content': '{"valid":%s}' % ('true' if len(calls) > 1 else 'false')},
                              'finish_reason': 'stop'}]}
    monkeypatch.setattr(OpenAICompatibleProvider, 'complete', fake)
    check = lambda v: [] if v['valid'] else ['valid must be true']
    with pytest.raises(AgentNeeded):
        runner.ask(tmp_path, 'plan', 'test', {}, check)
    assert runner.ask(tmp_path, 'plan', 'test', {}, check) == {'valid': True}
    assert runner.ask(tmp_path, 'plan', 'test', {}, check) == {'valid': True}
    assert len(calls) == 2 and 'Correct your previous answer once' in calls[1]['messages'][-1]['content']
    assert runner.read(tmp_path / 'provider-audit.json')['task_count'] == 1


def test_provider_rejects_inline_key_config_before_creating_requests(tmp_path):
    from pipeline.agent_shadow_providers import TaskRouter
    runner.write(tmp_path / 'providers.json', {'roles': {'write': {'type': 'http',
        'model': 'test', 'endpoint': 'https://api.example/chat/completions', 'key_env': 'ENV_KEY', 'api_key': 'forbidden'}}})
    with pytest.raises(ValueError, match='no secrets'):
        TaskRouter(tmp_path, 'rewrite-News-c001')
    assert not (tmp_path / 'tasks').exists()


def test_redirected_original_url_cannot_bypass_same_category_history(tmp_path, monkeypatch):
    _, _, _, _, original = setup(tmp_path, monkeypatch)
    from pipeline import agent_shadow_autonomous as autonomous
    snapshot = runner.read(tmp_path / 'input.json')
    snapshot['history']['News'] = [{'source_url': 'https://public.example/old-event', 'source_title': 'Old event'}]
    monkeypatch.setattr(autonomous, 'fetch_original', lambda b: {**original(b),
        'evidence_url': 'https://public.example/old-event'})
    policy = autonomous.AutonomousEditor(tmp_path, snapshot, runner.ask, runner.boundary, False)
    policy.plan()
    assert policy.pool('News', 3) == []
    assert policy.audit['url_exclusions']['news00'] == 'history_or_pool_duplicate'
