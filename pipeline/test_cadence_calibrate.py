"""Offline tests for compute_cadence_days — the median-gap math.

Run: python -m pipeline.test_cadence_calibrate

No network, no DB. Tests the pure compute function with synthetic
timestamps. The fetch path is exercised end-to-end via the production
calibrate() call which is integration-tested by manual dry-run.
"""
from __future__ import annotations

import sys

from .cadence_calibrate import compute_cadence_days


# Helper: build a list of timestamps representing entries at given day
# offsets from now, newest-first (matches fetch_pub_timestamps shape).
DAY = 86400.0


def days_ago(*offsets: float) -> list[float]:
    """E.g. days_ago(0, 1, 2) → 3 entries spanning today, yesterday, day-before."""
    base = 1_000_000_000.0  # arbitrary epoch baseline
    return sorted([base - off * DAY for off in offsets], reverse=True)


def test_daily_source():
    """Every day for 5 days → cadence=1."""
    pub = days_ago(0, 1, 2, 3, 4)
    assert compute_cadence_days(pub) == 1, compute_cadence_days(pub)
    print("PASS: daily source → cadence=1")


def test_weekly_source():
    """Once a week for 5 weeks → cadence=7."""
    pub = days_ago(0, 7, 14, 21, 28)
    assert compute_cadence_days(pub) == 7, compute_cadence_days(pub)
    print("PASS: weekly source → cadence=7")


def test_burst_publishing_clamps_to_1():
    """5 entries published 10 minutes apart → median gap < 1d, clamped to 1."""
    pub = days_ago(0, 0.007, 0.014, 0.020, 0.028)  # roughly 10-min gaps
    assert compute_cadence_days(pub) == 1, compute_cadence_days(pub)
    print("PASS: burst-publishing → cadence=1 (clamped)")


def test_monthly_clamps_to_30():
    """Three entries 60 days apart → cadence=30 (clamped from 60)."""
    pub = days_ago(0, 60, 120, 180)
    assert compute_cadence_days(pub) == 30, compute_cadence_days(pub)
    print("PASS: monthly+ source → cadence=30 (clamped)")


def test_irregular_uses_median_not_mean():
    """Gaps: 1d, 1d, 30d. Mean=10.7d, median=1d. Confirm median wins."""
    pub = days_ago(0, 1, 2, 32)
    assert compute_cadence_days(pub) == 1, compute_cadence_days(pub)
    print("PASS: irregular gaps use median (resists outliers)")


def test_too_few_entries_returns_none():
    assert compute_cadence_days([]) is None
    assert compute_cadence_days([1_000_000_000.0]) is None
    assert compute_cadence_days([1_000_000_000.0, 999_999_900.0]) is None
    print("PASS: ≤2 entries returns None (need ≥3 for ≥2 gaps)")


def test_three_entries_minimum():
    """Exactly 3 entries with consistent gap → reports the gap."""
    pub = days_ago(0, 4, 8)  # gaps of 4d and 4d
    assert compute_cadence_days(pub) == 4, compute_cadence_days(pub)
    print("PASS: 3-entry minimum produces a cadence")


def test_zero_gap_skipped():
    """Two entries published at same instant (rare) → that gap is dropped;
    if enough OTHER gaps remain, cadence still computes."""
    # 4 entries: today, today, 3d-ago, 6d-ago.
    # Raw gaps: 0, 3d, 3d. Filter the 0-gap dup → 3d, 3d. Median = 3d.
    pub = days_ago(0, 0, 3, 6)
    assert compute_cadence_days(pub) == 3, compute_cadence_days(pub)
    print("PASS: zero-gap dups filtered, remaining gaps still produce cadence")


def main() -> int:
    tests = [
        test_daily_source,
        test_weekly_source,
        test_burst_publishing_clamps_to_1,
        test_monthly_clamps_to_30,
        test_irregular_uses_median_not_mean,
        test_too_few_entries_returns_none,
        test_three_entries_minimum,
        test_zero_gap_skipped,
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
