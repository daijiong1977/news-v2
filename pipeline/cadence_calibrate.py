"""Auto-tune `cadence_days` from observed RSS publish-date gaps.

For each enabled RSS source in `redesign_source_configs`:
  1. Fetch the feed
  2. Pull up to 10 most-recent publish timestamps
  3. Compute median gap between consecutive entries (days)
  4. Round + clamp to [1, 30]
  5. Update `cadence_days` (or dry-run report)

Why median (not mean): a source that goes silent for 2 weeks then drops 5
articles in a day has gaps like [10min, 10min, 10min, 14d]. Mean is ~3
days; median is 10min → 1d. Median better reflects the source's typical
cadence and resists outlier gaps from vacation / news-cycle spikes.

Why clamp to [1, 30]:
  - Daily-or-faster sources collapse to cadence=1 (we won't poll faster).
  - Anything monthly+ collapses to 30 (we'll still poll monthly).
  - Matches the CHECK constraint in 20260504_cadence_aware_sources.sql
    (constraint allows up to 60; we choose a tighter ceiling here so a
    once-yearly source doesn't sleep for a full year).

Why RSS-only: html_list and sitemap sources don't carry uniform per-item
publish dates. RSS does (`<pubDate>` / `<updated>`). For html_list
sources, `cadence_days` stays manual — admin tunes it via Supabase
Studio when adding the source.

Run modes:
  python -m pipeline.cadence_calibrate                 # dry-run report
  python -m pipeline.cadence_calibrate --apply         # write back to DB
  python -m pipeline.cadence_calibrate --source-id 321 # one source only
  python -m pipeline.cadence_calibrate --apply --source-id 321
"""
from __future__ import annotations

import argparse
import logging
import statistics
import sys
import time
from typing import Iterable

import feedparser

from .supabase_io import client

log = logging.getLogger("cadence-calibrate")

CADENCE_MIN = 1
CADENCE_MAX = 30
PUB_DATES_PER_SOURCE = 10
MIN_GAPS_REQUIRED = 2  # need ≥ 2 gaps (3 entries) to compute a meaningful median


def fetch_pub_timestamps(rss_url: str,
                         n: int = PUB_DATES_PER_SOURCE) -> list[float]:
    """Pull up to `n` publish timestamps (unix seconds, newest first)
    from an RSS feed. Returns [] on parse error or empty feed."""
    try:
        feed = feedparser.parse(rss_url)
    except Exception as e:  # noqa: BLE001 — feedparser can throw a variety
        log.warning("feedparser failed on %s: %s", rss_url[:60], e)
        return []
    out: list[float] = []
    for entry in feed.entries[:n]:
        ts = getattr(entry, "published_parsed", None) \
             or getattr(entry, "updated_parsed", None)
        if ts:
            try:
                out.append(time.mktime(ts))
            except (OverflowError, ValueError):
                continue
    out.sort(reverse=True)
    return out


def compute_cadence_days(pub_dates: list[float]) -> int | None:
    """Median consecutive-entry gap in days, clamped to [1, 30].

    Returns None when fewer than `MIN_GAPS_REQUIRED + 1` valid timestamps
    are available (e.g. brand-new feed, parse failure, all entries dateless)."""
    if len(pub_dates) < MIN_GAPS_REQUIRED + 1:
        return None
    # pub_dates is sorted newest-first; gaps are always positive.
    gaps_seconds = [pub_dates[i] - pub_dates[i + 1]
                    for i in range(len(pub_dates) - 1)
                    if pub_dates[i] > pub_dates[i + 1]]
    if len(gaps_seconds) < MIN_GAPS_REQUIRED:
        return None
    median_gap_days = statistics.median(gaps_seconds) / 86400.0
    return max(CADENCE_MIN, min(CADENCE_MAX, round(median_gap_days)))


def _load_sources(source_id: int | None) -> list[dict]:
    sb = client()
    q = sb.table("redesign_source_configs").select(
        "id,name,category,rss_url,feed_kind,cadence_days,enabled"
    ).eq("enabled", True)
    if source_id is not None:
        q = q.eq("id", source_id)
    res = q.execute()
    return list(res.data or [])


def _persist_cadence(source_id: int, new_cadence: int) -> None:
    sb = client()
    sb.table("redesign_source_configs") \
        .update({"cadence_days": new_cadence}) \
        .eq("id", source_id) \
        .execute()


def calibrate(*, dry_run: bool = True,
              source_id: int | None = None) -> list[tuple]:
    """Run the calibration. Returns a report rows list of
    (name, old_cadence, new_cadence_or_None, status)."""
    rows = _load_sources(source_id)
    report: list[tuple] = []

    for r in rows:
        name = r.get("name") or f"id={r.get('id')}"
        old = int(r.get("cadence_days") or 1)
        feed_kind = (r.get("feed_kind") or "rss").lower()

        if feed_kind != "rss":
            report.append((name, old, None, f"skipped ({feed_kind})"))
            continue

        rss_url = r.get("rss_url")
        if not rss_url:
            report.append((name, old, None, "skipped (no rss_url)"))
            continue

        pub = fetch_pub_timestamps(rss_url)
        new = compute_cadence_days(pub)
        if new is None:
            report.append((name, old, None,
                           f"insufficient data ({len(pub)} dates)"))
            continue

        if new == old:
            report.append((name, old, new, "no change"))
            continue

        if dry_run:
            report.append((name, old, new, "would update"))
        else:
            try:
                _persist_cadence(int(r["id"]), new)
                report.append((name, old, new, "updated"))
            except Exception as e:  # noqa: BLE001
                report.append((name, old, new, f"WRITE FAILED: {e}"))

    return report


def _print_report(report: list[tuple]) -> None:
    print(f"\n{'Source':<36}{'Old':>5}{'New':>5}  Status")
    print("-" * 78)
    for name, old, new, status in report:
        n_disp = name[:35]
        new_s = str(new) if new is not None else "—"
        print(f"{n_disp:<36}{old:>5}{new_s:>5}  {status}")

    changed = sum(1 for _, _, _, s in report if "updated" in s or "would" in s)
    skipped = sum(1 for _, _, _, s in report if "skipped" in s or "insufficient" in s)
    nochange = sum(1 for _, _, _, s in report if s == "no change")
    failed = sum(1 for _, _, _, s in report if "FAILED" in s)
    print(f"\n{len(report)} sources · {changed} changed · {nochange} no-change "
          f"· {skipped} skipped · {failed} failed")


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--apply", action="store_true",
                   help="Write back to DB. Default: dry-run.")
    p.add_argument("--source-id", type=int, default=None,
                   help="Calibrate only this source row id.")
    args = p.parse_args()

    mode = "APPLY (writing to DB)" if args.apply else "DRY RUN (no DB writes)"
    print(f"Cadence calibration — {mode}")
    print(f"Sources: {'id=' + str(args.source_id) if args.source_id else 'all enabled'}")
    print(f"Window:  last {PUB_DATES_PER_SOURCE} entries per RSS feed")
    print(f"Bounds:  [{CADENCE_MIN}, {CADENCE_MAX}] days (median gap)")

    report = calibrate(dry_run=not args.apply, source_id=args.source_id)
    _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
