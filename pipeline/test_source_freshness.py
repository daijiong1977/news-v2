"""Source-first freshness: offline only, no models or publication writes."""
import pytest


def test_three_day_boundary_and_timezone():
    from pipeline.agent_shadow_source_first import freshness
    assert freshness('2026-09-30', '2026-10-03') == 'current'
    assert freshness('2026-09-29', '2026-10-03') == 'stale'
    assert freshness('2026-09-30T01:00:00Z', '2026-10-03') == 'stale'


def test_old_event_is_not_rescued_by_recent_publication():
    from pipeline.source_freshness import rejection
    row = {'published': '', 'link': 'https://www.dogonews.com/2026/9/30/giant-table'}
    assert rejection(row, '2026-10-03') is None
    assert rejection(row, '2026-10-03', {'body': 'On September 12, 2026, about 20,000 people gathered in Bucharest.'}) == 'stale_lead_event'


def test_unknown_future_and_historical_background():
    from pipeline.source_freshness import rejection
    assert rejection({'published': ''}, '2026-10-03', {'body': 'A discovery.'}) == 'unknown_source_date'
    assert rejection({'published': '2026-10-05'}, '2026-10-03') == 'future_source_date'
    assert rejection({'published': '2026-10-03'}, '2026-10-03', {'body': 'A new model helps researchers. In 1812 an earthquake crossed the fault.'}) is None


def test_original_publication_not_last_modified():
    from pipeline.source_freshness import publication_dates, rejection
    html = '<script type="application/ld+json">{"@type":"NewsArticle","datePublished":"2026-09-12","dateModified":"2026-10-03"}</script>'
    dates = publication_dates(html)
    assert dates == ['2026-09-12']
    assert rejection({'published': '2026-10-03'}, '2026-10-03', {'source_publication_dates': dates}) == 'stale_source_date'


def test_stale_candidate_never_fetches_image(tmp_path, monkeypatch):
    from pipeline import agent_shadow_source_first as sf, agent_shadow as runner
    from pipeline.test_agent_shadow_source_first import sources, fake_collection
    fake_collection(monkeypatch)
    monkeypatch.setattr(sf, 'fetch_source_entries', lambda *a, **kw: [
        {'title': 'Old event', 'link': 'https://example.org/2026/9/30/table', 'published': '2026-10-02'}])
    monkeypatch.setattr(sf, 'fetch_original', lambda b: {**b, 'body': 'On September 12, 2026, people gathered. ' + 'fact ' * 200})
    monkeypatch.setattr(sf, 'safe_image', lambda *a: pytest.fail('Old event must be rejected before photo fetch'))
    assert sf.collect(tmp_path, {'Fun': sources('Fun', 1)}, '2026-10-03') == []
    row = runner.read(tmp_path/'source-collection.json')['sections']['Fun']['sources'][0]['results'][0]
    assert row['reason'] == 'stale_lead_event'


def test_stale_feed_rejected_before_body_and_policy_frozen(tmp_path, monkeypatch):
    from pipeline import agent_shadow_source_first as sf, agent_shadow as runner
    from pipeline.test_agent_shadow_source_first import sources
    monkeypatch.setattr(sf, 'fetch_source_entries', lambda *a, **kw: [
        {'title': 'Old story', 'link': 'https://example.org/old', 'published': '2026-09-29'}])
    monkeypatch.setattr(sf, 'fetch_original', lambda *a: pytest.fail('Stale feed must not fetch body'))
    sf.collect(tmp_path, {'News': sources('News', 1)}, '2026-10-03')
    state = runner.read(tmp_path/'source-collection.json')
    assert state['freshness_policy'] == 'three-day-source-and-explicit-lead-v1'
    assert state['sections']['News']['sources'][0]['results'][0]['reason'] == 'stale_source_date'
    assert sf.collect(tmp_path, {'News': sources('News', 1)}, '2026-10-03') == []
