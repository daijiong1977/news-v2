"""Seed redesign_source_configs table from current Python config.

Reads news_sources, science_sources, fun_sources and upserts all rows into
redesign_source_configs. Keeps current config as canonical source of truth
for this run; migration to read FROM Supabase is a follow-up.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from supabase import create_client

from .fun_sources import (
    BBC_TENNIS, FUN_BACKUPS, WEEKDAY_SOURCES as FUN_WEEKDAY_SOURCES,
)
from .news_sources import SOURCES as NEWS_SOURCES
from .science_sources import (
    SCIENCE_ALWAYS, SCIENCE_BACKUPS, SCIENCE_WEEKDAY,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("seed")

for _line in open("/Users/jiong/myprojects/news-v2/.env"):
    if "=" in _line and not _line.startswith("#"):
        _k, _v = _line.strip().split("=", 1)
        os.environ[_k] = _v


def row(src, category: str, active_weekdays: list[int] | None = None) -> dict[str, Any]:
    return {
        "id": src.id,
        "category": category,
        "name": src.name,
        "rss_url": src.rss_url,
        "flow": src.flow,
        "max_to_vet": src.max_to_vet,
        "min_body_words": src.min_body_words,
        "priority": src.priority,
        "enabled": src.enabled,
        "is_backup": src.is_backup,
        "active_weekdays": active_weekdays,
        "notes": src.notes or None,
    }


def main() -> None:
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
    rows: list[dict] = []

    # ─── News ───
    for s in NEWS_SOURCES:
        rows.append(row(s, "News", None))

    # ─── Science ───
    # Always-on (every day)
    for s in SCIENCE_ALWAYS:
        rows.append(row(s, "Science", None))
    # Weekday-specific
    for wd, s in SCIENCE_WEEKDAY.items():
        rows.append(row(s, "Science", [wd]))
    # Backups (always available)
    for s in SCIENCE_BACKUPS:
        rows.append(row(s, "Science", None))

    # ─── Fun ───
    # Per-weekday sources
    seen_ids: set[int] = set()
    for wd, srcs in FUN_WEEKDAY_SOURCES.items():
        for s in srcs:
            if s.id == BBC_TENNIS.id:
                # BBC Tennis handled below as single row with union of weekdays
                continue
            # Upsert with weekday appended
            existing = next((r for r in rows if r["id"] == s.id and r["category"] == "Fun"), None)
            if existing:
                wds = set(existing.get("active_weekdays") or [])
                wds.add(wd)
                existing["active_weekdays"] = sorted(wds)
            else:
                rows.append(row(s, "Fun", [wd]))
                seen_ids.add(s.id)
    # BBC Tennis: find its active weekdays from FUN_WEEKDAY_SOURCES
    tennis_days = sorted([wd for wd, srcs in FUN_WEEKDAY_SOURCES.items()
                          if any(sr.id == BBC_TENNIS.id for sr in srcs)])
    rows.append(row(BBC_TENNIS, "Fun", tennis_days))
    # Fun backups
    for s in FUN_BACKUPS:
        rows.append(row(s, "Fun", None))

    # Deduplicate by (id, category) — in case seeding logic double-counts
    seen: set[tuple] = set()
    dedup_rows = []
    for r in rows:
        key = (r["id"], r["category"])
        if key in seen:
            continue
        seen.add(key)
        dedup_rows.append(r)

    log.info("Prepared %d source-config rows", len(dedup_rows))
    # Upsert in batches
    res = sb.table("redesign_source_configs").upsert(dedup_rows).execute()
    log.info("Upserted: %d rows", len(res.data or []))

    # Summary by category
    by_cat: dict[str, int] = {}
    for r in dedup_rows:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + 1
    for cat, n in by_cat.items():
        log.info("  %s: %d rows", cat, n)


if __name__ == "__main__":
    main()
