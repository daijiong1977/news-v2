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
        out = db_config.load_sources("Fun", today=today, n=3)
    assert _names(out) == ["New", "Older", "Old"], _names(out)
    print("PASS: never-used sorts before any dated entry")


def test_eligible_only_picked():
    """Only sources with next_pickup_at <= today are in the eligible pool."""
    today = date(2026, 5, 3)
    rows = [
        _row("Today",      priority=1, next_pickup="2026-05-03"),
        _row("Tomorrow",   priority=1, next_pickup="2026-05-04"),  # NOT eligible
        _row("Yesterday",  priority=2, next_pickup="2026-05-02"),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, n=3)
    # Step 3 takes 2 eligible, Step 4 fills with Tomorrow
    assert _names(out) == ["Yesterday", "Today", "Tomorrow"], _names(out)
    print("PASS: Step 4 fills shortfall from closest non-eligible")


def test_priority_tiebreak_within_eligible():
    """Same next_pickup, low priority wins."""
    today = date(2026, 5, 3)
    rows = [
        _row("LowPri",  priority=2, next_pickup="2026-05-03"),
        _row("HighPri", priority=1, next_pickup="2026-05-03"),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, n=2)
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
        out = db_config.load_sources("Fun", today=today, n=2)
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
        out = db_config.load_sources("Fun", today=today, n=2)
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
        out = db_config.load_sources("Fun", today=today, n=3)
    assert _names(out) == ["Active"], _names(out)
    print("PASS: disabled sources excluded")


def test_is_backup_now_included():
    """Q1=b: is_backup is no longer a filter. Backup rows participate."""
    today = date(2026, 5, 3)
    rows = [
        _row("Primary", is_backup=False, priority=1),
        _row("Backup",  is_backup=True,  priority=2),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, n=2)
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
        out = db_config.load_sources("Fun", today=today, n=3)
    assert _names(out) == ["FunSrc"], _names(out)
    print("PASS: cross-category sources excluded")


def test_under_fill_accepted():
    """Category with fewer than N enabled sources returns what it has."""
    today = date(2026, 5, 3)
    rows = [
        _row("Only",  next_pickup="2026-05-03"),
    ]
    with _patch_rows(rows):
        out = db_config.load_sources("Fun", today=today, n=3)
    assert len(out) == 1
    print("PASS: under-fill returns < N gracefully")


def main():
    import sys
    tests = [
        test_never_used_sorts_first,
        test_eligible_only_picked,
        test_priority_tiebreak_within_eligible,
        test_lru_secondary_tiebreak,
        test_cadence_days_tiebreak,
        test_disabled_excluded,
        test_is_backup_now_included,
        test_cross_category_excluded,
        test_under_fill_accepted,
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
