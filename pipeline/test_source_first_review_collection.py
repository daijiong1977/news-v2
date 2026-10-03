"""Spec/code review regressions; fake feeds/models only."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
from zoneinfo import ZoneInfo

import pytest

from pipeline import agent_shadow as runner
from pipeline.test_agent_shadow_source_first import full_fixture, sources


def test_interrupted_prepare_uses_frozen_context_without_registry_or_connector(tmp_path, monkeypatch):
    from pipeline import db_config, agent_shadow_source_first as sf
    from pipeline.publication_history import PublicationHistoryGuard
    frozen = {'date': '2026-10-01', 'test_profile': 'source-first-grok', 'http_fallback': None,
              'started_at': '2026-10-01T01:00:00-04:00',
              'history': {c: [{'category': c, 'source_title': 'An earlier event',
                               'source_url': 'https://old.example/event'}] for c in runner.CATS},
              'sources': {c: [asdict(s) for s in sources(c, 1)] for c in runner.CATS}}
    runner.write(tmp_path / 'prepare-context.json', frozen)
    def forbidden(*args, **kwargs):
        pytest.fail('Frozen prepare must not reload the connector or sources')
    monkeypatch.setattr(db_config, 'load_sources', forbidden)
    monkeypatch.setattr(PublicationHistoryGuard, 'load', forbidden)
    def collect(root, selected, today):
        assert {c: [asdict(s) for s in rows] for c, rows in selected.items()} == frozen['sources']
        runner.write(root / 'source-collection.json', {'sections': {
            c: {'sources': [{'source': s, 'results': []} for s in rows]}
            for c, rows in frozen['sources'].items()}})
        return []
    monkeypatch.setattr(sf, 'collect', collect)
    result = runner.prepare(tmp_path, '2026-10-01', registry_file=tmp_path / 'removed-registry.json',
                            editor_mode='autonomous', test_profile='source-first-grok')
    assert result['ok']
    assert runner.read(tmp_path / 'input.json')['history'] == frozen['history']
    assert runner.read(tmp_path / 'metrics.json')['started_at'] == frozen['started_at']
    with pytest.raises(ValueError, match='stale_run'):
        runner.check_stale(tmp_path, False, None)


def test_history_checks_original_feed_and_redirected_evidence_urls(tmp_path, monkeypatch):
    from pipeline.agent_shadow_source_editor import SourceFirstEditor
    snapshot, _, _, answer = full_fixture(tmp_path, monkeypatch)
    policy = SourceFirstEditor(tmp_path, snapshot, answer, runner.boundary, False)
    policy.plan()
    sid = policy.catalog['News'][0]['id']
    bodies = runner.read(tmp_path / 'bodies.json')
    snapshot['history']['News'][0]['source_url'] = bodies[sid]['link']
    bodies[sid]['evidence_url'] = 'https://canonical.example/new-url'
    runner.write(tmp_path / 'bodies.json', bodies)
    assert sid not in {b['id'] for b in policy.originals('News')}


def test_changed_original_body_is_rejected_before_paid_writer(tmp_path, monkeypatch):
    from pipeline.agent_shadow_source_editor import SourceFirstEditor
    snapshot, _, _, answer = full_fixture(tmp_path, monkeypatch)
    policy = SourceFirstEditor(tmp_path, snapshot, answer, runner.boundary, False)
    policy.plan()
    sid = policy.catalog['News'][0]['id']
    bodies = runner.read(tmp_path / 'bodies.json')
    bodies[sid]['evidence_sha256'] = hashlib.sha256(bodies[sid]['body'].encode()).hexdigest()
    bodies[sid]['body'] = 'tampered ' * 400
    runner.write(tmp_path / 'bodies.json', bodies)
    with pytest.raises(ValueError, match='body cache'):
        policy.originals('News')


def test_refill_selector_receives_bounded_accepted_topics_publishers_and_events(tmp_path, monkeypatch):
    from pipeline.agent_shadow_source_editor import SourceFirstEditor
    snapshot, _, _, answer = full_fixture(tmp_path, monkeypatch)
    policy = SourceFirstEditor(tmp_path, snapshot, answer, runner.boundary, False)
    policy.plan()
    original = policy.originals('Science')[0]
    original['publisher'] = original['article']['_publisher_key']
    runner.write(tmp_path / 'editor-state.json', {c: {'accepted': [
        {'candidate': original, 'entry': {'middle_en': {'headline': 'Finished science story'},
                                         'body': 'DO_NOT_RESEND' * 1000}, 'details': {'private': 'DO_NOT_RESEND'}}
    ] if c == 'Science' else []} for c in runner.CATS})
    captured = []
    def inspect(root, key, prompt, material, validate, **kw):
        if key.startswith('select-batch-Science'):
            captured.append(deepcopy(material))
        return answer(root, key, prompt, material, validate, **kw)
    policy.ask = inspect
    policy.pool('Science', 8)
    accepted = captured[0]['accepted']
    assert len(accepted) == 1
    assert accepted[0]['topic'] == original['topic']
    assert accepted[0]['publisher'] == original['article']['_publisher_key']
    assert accepted[0]['title'] == 'Finished science story'
    assert len(accepted[0]['source_excerpt']) <= 1200
    assert 'DO_NOT_RESEND' not in str(captured[0])


def test_incremental_catalog_stays_bounded_and_retains_retired_routing(tmp_path, monkeypatch):
    from pipeline.agent_shadow_source_editor import SourceFirstEditor
    snapshot, _, _, answer = full_fixture(tmp_path, monkeypatch)
    policy = SourceFirstEditor(tmp_path, snapshot, answer, runner.boundary, False)
    policy.plan()
    seed = snapshot['candidates'][0]
    score = policy.catalog['Fun'][0]
    old = [{**deepcopy(seed), 'id': f'old-{i}'} for i in range(30)]
    fresh = [{**deepcopy(seed), 'id': f'fresh-{i}', 'category': 'Fun'} for i in range(4)]
    policy.snapshot['candidates'].extend(old)
    policy.catalog['Fun'] = [{**score, 'id': b['id']} for b in old]
    runner.write(tmp_path / 'batch-Fun-8.json', {'pool': [], 'drafts': [], 'considered': [b['id'] for b in old]})
    runner.write(tmp_path / 'editor-state.json', {c: {'accepted': []} for c in runner.CATS})
    pending = tmp_path / 'pending-source-plan-Fun.json'
    runner.write(pending, {'candidates': fresh, 'applied': False})
    policy.plan_increment('Fun', 8, pending)
    assert len(policy.catalog['Fun']) <= 30
    assert {b['id'] for b in fresh} <= {b['id'] for b in policy.catalog['Fun']}
    retired = runner.read(tmp_path / 'autonomous-audit.json')['retired_catalog']['Fun']
    assert retired and all(row['id'].startswith('old-') for row in retired)
    candidates = {b['id']: b for b in runner.read(tmp_path / 'autonomous-catalog.json')['candidates']}
    assert all(candidates[row['id']]['planned_category'] == 'Fun' for row in retired)


def test_stale_review_of_retired_ready_story_uses_final_routed_section(tmp_path, monkeypatch):
    now = datetime.now(ZoneInfo('America/New_York')).date()
    candidate = {'id': 'retired', 'category': 'News', 'planned_category': 'Fun',
                 'title': 'Animal competition', 'link': 'https://example.org/story'}
    runner.write(tmp_path / 'metrics.json', {'started_at': (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()})
    runner.write(tmp_path / 'input.json', {'date': now.isoformat(), 'candidates': [candidate],
                 'sources': {}, 'history': {c: [] for c in runner.CATS}})
    runner.write(tmp_path / 'autonomous-catalog.json', {'catalog': {c: [] for c in runner.CATS},
                 'candidates': [candidate], 'sources': {}})
    runner.write(tmp_path / 'editor-state.json', {c: {'accepted': [{'candidate': candidate}] if c == 'Fun' else [],
                 'outcomes': []} for c in runner.CATS})
    registry = tmp_path / 'fresh.json'
    runner.write(registry, {'date': now.isoformat(), 'history': [{'category': 'Fun',
                 'published_date': (now - timedelta(days=1)).isoformat(),
                 'source_title': candidate['title'], 'source_url': candidate['link']}]})
    captures = []
    def review(root, key, prompt, material, validate):
        captures.append(material)
        return {'blocked_ids': ['retired']}
    monkeypatch.setattr(runner, 'ask', review)
    runner.check_stale(tmp_path, True, registry)
    assert captures[0]['candidates'][0]['category'] == 'Fun'
    state = runner.read(tmp_path / 'editor-state.json')
    assert not state['Fun']['accepted']
    assert state['Fun']['outcomes'][0]['id'] == 'retired'
    assert not state['News']['outcomes']
