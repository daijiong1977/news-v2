"""Tests for the mega-path P0 regression fixes (2026-07-08).

Covers the pure/mockable parts of:
  1. phase_a_light routing through fetch_source_entries (freshness filter +
     feed_kind dispatch restored — was raw feedparser.parse).
  2. Past-run dedup for mega briefs (_drop_dup_briefs).
  3. Closed-loop pickup stamping (_probe_bump rule: failing sources stop
     hogging the most-overdue rotation slot).

Run: python -m pipeline.test_mega_pickup_fixes   (also works under pytest)
"""
from __future__ import annotations

from types import SimpleNamespace

from pipeline import full_round


# ── 1. phase_a_light uses the feed-kind-aware, freshness-filtered fetcher ──

def test_phase_a_light_routes_through_fetch_source_entries():
    calls = []

    def fake_fetch(source, max_entries=25, **kw):
        calls.append((source.name, max_entries))
        return [{"title": "T1", "link": "http://x/1", "published": "2026-07-08",
                 "summary": "S1"}]

    orig = full_round.fetch_source_entries
    full_round.fetch_source_entries = fake_fetch
    try:
        src = SimpleNamespace(name="FakeSrc", rss_url="http://x/feed",
                              feed_kind="html_list", feed_config=None,
                              flow="full", max_to_vet=6, min_body_words=300)
        briefs = full_round.phase_a_light("Fun", [src], max_per_source=4)
    finally:
        full_round.fetch_source_entries = orig

    assert calls == [("FakeSrc", 4)]              # dispatcher used, cap passed
    assert len(briefs) == 1
    b = briefs[0]
    assert b["title"] == "T1" and b["link"] == "http://x/1"
    assert b["_source_name"] == "FakeSrc"          # mega annotations intact
    assert b["_source"] is src
    assert b["_category"] == "Fun"


def test_phase_a_light_survives_one_bad_source():
    def fake_fetch(source, max_entries=25, **kw):
        if source.name == "Broken":
            raise RuntimeError("boom")
        return [{"title": "ok", "link": "http://y/1", "published": "", "summary": ""}]

    orig = full_round.fetch_source_entries
    full_round.fetch_source_entries = fake_fetch
    try:
        good = SimpleNamespace(name="Good", rss_url="u", feed_kind="rss",
                               feed_config=None, flow="full",
                               max_to_vet=6, min_body_words=300)
        bad = SimpleNamespace(name="Broken", rss_url="u", feed_kind="rss",
                              feed_config=None, flow="full",
                              max_to_vet=6, min_body_words=300)
        briefs = full_round.phase_a_light("News", [bad, good])
    finally:
        full_round.fetch_source_entries = orig

    assert [b["_source_name"] for b in briefs] == ["Good"]   # no raise, bad skipped


# ── 2. Past-run dedup on briefs ──

def test_drop_dup_briefs_drops_near_matches_keeps_rest():
    briefs = [
        {"title": "Giant panda born at the San Diego Zoo"},
        {"title": "New telescope spots a distant galaxy"},
    ]
    past = ["Giant panda born at San Diego Zoo"]   # near-identical to brief 0
    kept, dropped = full_round._drop_dup_briefs(briefs, past, threshold=0.80)
    assert [b["title"] for b in dropped] == ["Giant panda born at the San Diego Zoo"]
    assert [b["title"] for b in kept] == ["New telescope spots a distant galaxy"]


def test_drop_dup_briefs_no_past_titles_keeps_all():
    briefs = [{"title": "A"}, {"title": "B"}]
    kept, dropped = full_round._drop_dup_briefs(briefs, [], threshold=0.80)
    assert kept == briefs and dropped == []


# ── 3. Probe-bump rule (failing source must stop hogging the rotation) ──

def test_probe_bump_stale_or_empty_moves_to_tomorrow():
    assert full_round._probe_bump("2026-06-01", "2026-07-08") == "2026-07-09"
    assert full_round._probe_bump(None, "2026-07-08") == "2026-07-09"
    assert full_round._probe_bump("2026-07-08", "2026-07-08") == "2026-07-09"


def test_probe_bump_future_schedule_left_alone():
    assert full_round._probe_bump("2026-07-20", "2026-07-08") is None
    # timestamp-formatted values must also compare on the date part
    assert full_round._probe_bump("2026-07-20T05:00:00+00:00", "2026-07-08") is None


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS {fn.__name__}")
    print(f"OK — {len(fns)} tests passed")


if __name__ == "__main__":
    _run_all()
