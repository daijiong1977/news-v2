"""Offline algorithm tests for db_config.load_sources cadence-aware path.

Run: python -m pipeline.test_load_sources

Patches db_config.client to return synthetic rows; never hits the real DB.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from . import db_config


def _row(name, *, cat="Fun", priority=1, cadence_days=1,
         enabled=True, is_backup=False, last_used=None,
         next_pickup=None, state="live"):
    return {
        "id": hash(name) & 0xFFFF, "name": name, "category": cat,
        "rss_url": f"https://example.com/{name}",
        "feed_kind": "rss", "feed_config": None,
        "flow": "full", "max_to_vet": 10, "min_body_words": 300,
        "priority": priority, "cadence_days": cadence_days,
        "enabled": enabled, "is_backup": is_backup,
        "last_used_at": last_used, "next_pickup_at": next_pickup,
        "state": state, "notes": "",
    }


def _patch_rows(rows):
    """Return a context manager that makes db_config.client() return these rows."""
    sb = MagicMock()
    sb.table.return_value.select.return_value.execute.return_value.data = rows
    db_config._src_cache = None  # bypass cache
    return patch.object(db_config, "client", return_value=sb)


def _names(srcs):
    return [s.name for s in srcs]


def test_never_used_sorts_first():
    """NULL next_pickup_at + NULL last_used_at sort to top of eligible pool."""
    today = date(2026, 5, 3)
    rows = [
        _row("Old",   priority=1, last_used="2026-04-29", next_pickup="2026-05-01"),
        _row("New",   priority=2, last_used=None,         next_pickup=None),
        _row("Older", priority=1, last_used="2026-04-26", next_pickup="2026-04-28"),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, max_pool=3)
    assert _names(out) == ["New", "Older", "Old"], _names(out)
    print("PASS: never-used sorts before any dated entry")


def test_eligible_first_skips_sleeping_when_enough():
    """If eligible >= min_pool, sleeping sources are NOT tapped."""
    today = date(2026, 5, 3)
    rows = [
        _row(f"E{i}", priority=1, next_pickup="2026-05-03") for i in range(7)
    ] + [
        _row("Sleep1", priority=1, next_pickup="2026-05-10"),
        _row("Sleep2", priority=1, next_pickup="2026-05-15"),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, min_pool=6)
    # All 7 eligible should be returned; neither sleeping source picked.
    names = _names(out)
    assert len(names) == 7, names
    assert all(n.startswith("E") for n in names), names
    assert "Sleep1" not in names and "Sleep2" not in names
    print("PASS: sleeping skipped when eligible >= min_pool")


def test_sleeping_fills_only_shortfall():
    """When eligible < min_pool, sleeping fills only up to min_pool."""
    today = date(2026, 5, 3)
    rows = [
        _row("E1", priority=1, next_pickup="2026-05-03"),
        _row("E2", priority=1, next_pickup="2026-05-02"),
        _row("Sleep1", priority=1, next_pickup="2026-05-04"),
        _row("Sleep2", priority=1, next_pickup="2026-05-05"),
        _row("Sleep3", priority=1, next_pickup="2026-05-06"),
        _row("Sleep4", priority=1, next_pickup="2026-05-07"),
        _row("Sleep5", priority=1, next_pickup="2026-05-08"),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, min_pool=6)
    # 2 eligible + 4 sleeping (closest first) = 6 total. Sleep5 left out.
    names = _names(out)
    assert len(names) == 6, names
    assert "Sleep5" not in names, names
    print("PASS: sleeping fills exactly the shortfall (not more)")


def test_priority_tiebreak_within_eligible():
    """Same next_pickup, low priority wins."""
    today = date(2026, 5, 3)
    rows = [
        _row("LowPri",  priority=2, next_pickup="2026-05-03"),
        _row("HighPri", priority=1, next_pickup="2026-05-03"),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, max_pool=2)
    assert _names(out) == ["HighPri", "LowPri"], _names(out)
    print("PASS: priority tiebreak within same next_pickup")


def test_lru_secondary_tiebreak():
    """Same next_pickup AND priority, oldest last_used wins."""
    today = date(2026, 5, 3)
    rows = [
        _row("Recent", priority=1, next_pickup="2026-05-03",
             last_used="2026-05-02"),
        _row("Old",    priority=1, next_pickup="2026-05-03",
             last_used="2026-04-26"),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, max_pool=2)
    assert _names(out) == ["Old", "Recent"], _names(out)
    print("PASS: LRU tiebreak — oldest last_used wins")


def test_cadence_days_tiebreak():
    """Same priority + same next_pickup: daily-cadence wins over weekly."""
    today = date(2026, 5, 3)
    rows = [
        _row("Weekly", priority=1, cadence_days=7, next_pickup="2026-05-03"),
        _row("Daily",  priority=1, cadence_days=1, next_pickup="2026-05-03"),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, max_pool=2)
    assert _names(out) == ["Daily", "Weekly"], _names(out)
    print("PASS: cadence_days tiebreak — daily beats weekly at priority tie")


def test_disabled_excluded():
    """enabled=false sources never appear."""
    today = date(2026, 5, 3)
    rows = [
        _row("Active",  enabled=True),
        _row("Disabled", enabled=False),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, max_pool=3)
    assert _names(out) == ["Active"], _names(out)
    print("PASS: disabled sources excluded")


def test_paused_excluded():
    """state='paused' sources are auto-paused: invisible to load_sources."""
    today = date(2026, 5, 3)
    rows = [
        _row("Live",   state="live"),
        _row("Paused", state="paused"),  # auto-paused by phase_a_probe
        _row("Null",   state=None),       # legacy NULL state — still live
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, max_pool=5)
    names = sorted(_names(out))
    assert names == ["Live", "Null"], names
    print("PASS: state='paused' excluded; NULL/'live' included")


def test_is_backup_now_included():
    """Q1=b: is_backup is no longer a filter. Backup rows participate."""
    today = date(2026, 5, 3)
    rows = [
        _row("Primary", is_backup=False, priority=1),
        _row("Backup",  is_backup=True,  priority=2),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, max_pool=2)
    assert _names(out) == ["Primary", "Backup"], _names(out)
    print("PASS: is_backup field is ignored (Q1=b)")


def test_cross_category_excluded():
    """Sources from other categories never appear."""
    today = date(2026, 5, 3)
    rows = [
        _row("FunSrc", cat="Fun"),
        _row("NewsSrc", cat="News"),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, max_pool=3)
    assert _names(out) == ["FunSrc"], _names(out)
    print("PASS: cross-category sources excluded")


def test_under_fill_accepted():
    """Category with fewer than min_pool sources returns what it has."""
    today = date(2026, 5, 3)
    rows = [
        _row("Only",  next_pickup="2026-05-03"),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, min_pool=6)
    assert len(out) == 1, out
    print("PASS: under-fill returns < min_pool gracefully")


def test_max_pool_caps_eligible():
    """max_pool caps the return size even when more eligible exist."""
    today = date(2026, 5, 3)
    rows = [
        _row(f"E{i}", priority=1, next_pickup="2026-05-03") for i in range(15)
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, max_pool=5)
    assert len(out) == 5, len(out)
    print("PASS: max_pool caps the eligible pool")


def main():
    import sys
    tests = [
        test_never_used_sorts_first,
        test_eligible_first_skips_sleeping_when_enough,
        test_sleeping_fills_only_shortfall,
        test_priority_tiebreak_within_eligible,
        test_lru_secondary_tiebreak,
        test_cadence_days_tiebreak,
        test_disabled_excluded,
        test_paused_excluded,
        test_is_backup_now_included,
        test_cross_category_excluded,
        test_under_fill_accepted,
        test_max_pool_caps_eligible,
    ]
    try:
        for t in tests:
            t()
    except AssertionError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    print(f"\nAll {len(tests)} tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
