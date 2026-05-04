"""Offline tests for aggregate_category's runtime-backfill behavior.

When sources at the front of the cadence-sorted pool fail to produce
candidates (e.g. weekly source with no fresh content in the 5-day
window), aggregate_category must iterate down the pool until `want`
sources have contributed OR the pool is exhausted.

Run: python -m pipeline.test_aggregate_backfill
"""
from __future__ import annotations

import sys

from .full_round import aggregate_category
from .news_sources import NewsSource


def _src(name: str) -> NewsSource:
    return NewsSource(
        id=hash(name) & 0xFFFF, name=name,
        rss_url=f"https://example.com/{name}",
        flow="full", max_to_vet=10, min_body_words=300,
        priority=1, enabled=True, is_backup=False,
    )


def test_backfill_skips_failing_sources():
    """First two sources fail (None); algorithm continues to the next 3."""
    pool = [_src(n) for n in "ABCDE"]
    calls: list[str] = []

    def runner(s):
        calls.append(s.name)
        if s.name in ("A", "B"):
            return None  # simulate fetch fail / no fresh articles
        return {"source": s, "candidates": [{"winner": {"id": s.name}, "slot": "choice_1"}]}

    out = aggregate_category("Test", pool, runner, want=3)
    assert set(out.keys()) == {"C", "D", "E"}, list(out.keys())
    assert calls == ["A", "B", "C", "D", "E"], calls
    print("PASS: backfill iterates past failures until want=3 reached")


def test_stops_iterating_when_want_satisfied():
    """As soon as `want` sources contribute, stop calling runner."""
    pool = [_src(n) for n in "ABCDEFGHIJ"]
    calls: list[str] = []

    def runner(s):
        calls.append(s.name)
        return {"source": s, "candidates": [{"winner": {"id": s.name}, "slot": "choice_1"}]}

    out = aggregate_category("Test", pool, runner, want=3)
    assert len(out) == 3
    assert calls == ["A", "B", "C"], calls  # didn't touch D-J
    print("PASS: stops iterating once want=3 sources have contributed")


def test_pool_exhausted_under_fills():
    """If every source returns None, return what we have (≤ want)."""
    pool = [_src(n) for n in "ABCDE"]

    def runner(s):
        return None

    out = aggregate_category("Test", pool, runner, want=3)
    assert out == {}
    print("PASS: pool fully fails → empty dict, no crash")


def test_max_attempts_caps_iteration():
    """`max_attempts=2` stops after 2 sources tried even if none contributed."""
    pool = [_src(n) for n in "ABCDE"]
    calls: list[str] = []

    def runner(s):
        calls.append(s.name)
        return None

    out = aggregate_category("Test", pool, runner, want=3, max_attempts=2)
    assert calls == ["A", "B"], calls
    assert out == {}
    print("PASS: max_attempts caps iteration even when want unmet")


def test_want_satisfied_with_partial_pool_failures():
    """Mix of pass + fail; algorithm stops once 3 sources have contributed."""
    pool = [_src(n) for n in "ABCDEFGH"]
    calls: list[str] = []

    def runner(s):
        calls.append(s.name)
        if s.name in ("B", "D"):
            return None
        return {"source": s, "candidates": [{"winner": {"id": s.name}, "slot": "choice_1"}]}

    out = aggregate_category("Test", pool, runner, want=3)
    # A succeeds, B fails, C succeeds, D fails, E succeeds → stop
    assert set(out.keys()) == {"A", "C", "E"}, list(out.keys())
    assert calls == ["A", "B", "C", "D", "E"], calls
    print("PASS: backfill correctly skips fails + stops at want")


def main() -> int:
    tests = [
        test_backfill_skips_failing_sources,
        test_stops_iterating_when_want_satisfied,
        test_pool_exhausted_under_fills,
        test_max_attempts_caps_iteration,
        test_want_satisfied_with_partial_pool_failures,
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
