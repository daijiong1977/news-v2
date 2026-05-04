"""Queue body-length / keyword / image issues for in-process autofix
to handle (pipeline.autofix_apply, runs DeepSeek / og:image regrab),
or for the local Claude Code scheduled task to escalate (3am / 10am
fires) for harder cases.

This module is intentionally NOT a fixer — every quality miss is
queued. We never mechanically trim article content: a hard cut at
word N produces mid-thought endings that ship to kids. why_it_matters
and listing-summary overshoots are reported in the digest only —
the digest itself is the signal, no autofix action is taken on them.

Queue rules:
  - body_too_long  / body_too_short  → enqueue (LLM rewrite)
  - keyword_miss                     → enqueue (LLM weave or remove)
  - image_missing                    → enqueue (image regen)
  - summary / why_it_matters too long → REPORT ONLY (no enqueue)

Usage:
    python -m pipeline.quality_autofix --days 1
    python -m pipeline.quality_autofix --days 1 --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any
from urllib import error, request

from pipeline.quality_digest import (
    ET, BODY_TARGETS, WC_SLACK,
    LEVELS, CATS, STORAGE_BASE,
    score_article, _fetch_json,
)

log = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# --- HTTP helpers (write side) -----------------------------------

def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }


def _enqueue(published_date: str, story_id: str, level: str,
              problem_type: str, problem_detail: dict) -> bool:
    """Insert a row into redesign_autofix_queue. Idempotent via UNIQUE
    constraint (same date+story+level+problem won't dup if a queued
    row already exists)."""
    body = json.dumps([{
        "published_date": published_date,
        "story_id":       story_id,
        "level":          level,
        "problem_type":   problem_type,
        "problem_detail": problem_detail,
        "status":         "queued",
    }]).encode()
    req = request.Request(
        f"{SUPABASE_URL}/rest/v1/redesign_autofix_queue",
        method="POST", data=body,
        headers={
            **_sb_headers(),
            "Content-Type": "application/json",
            # PostgREST: ignore the dup violation, treat as upsert no-op.
            "Prefer":       "resolution=ignore-duplicates,return=minimal",
        },
    )
    try:
        with request.urlopen(req, timeout=20) as r:
            return r.status in (200, 201, 204)
    except error.HTTPError as e:
        # 409 = unique violation. Already queued. That's fine.
        if e.code == 409:
            return True
        log.error("enqueue failed: %s %s", e.code, e.read().decode()[:200])
        return False


# --- Orchestration -----------------------------------------------

def autofix_day(date_iso: str, dry_run: bool) -> dict:
    """Read one day's content, queue every quality miss for the local
    Mac daemon. No mechanical mutations — see module docstring."""
    report: dict[str, Any] = {
        "date": date_iso,
        "queued": [],
        "skipped": [],
    }

    for cat in CATS:
        # Pull listings to discover story IDs.
        listings: dict[str, dict] = {}
        for level in LEVELS:
            url = f"{STORAGE_BASE}/{date_iso}/payloads/articles_{cat}_{level}.json"
            listings[level] = _fetch_json(url) or {}
        easy_articles = listings.get("easy", {}).get("articles", [])
        story_ids = [a["id"] for a in easy_articles[:3]]

        for sid in story_ids:
            for level in LEVELS:
                payload_url_path = f"article_payloads/payload_{sid}/{level}.json"
                full_url = f"{STORAGE_BASE}/{date_iso}/{payload_url_path}"
                payload = _fetch_json(full_url)
                if not payload:
                    report["skipped"].append({
                        "id": sid, "level": level, "reason": "payload missing"
                    })
                    continue

                # Find the listing entry for this story+level — that's
                # where the short card summary lives.
                listing_articles = listings.get(level, {}).get("articles", [])
                listing_entry = next((a for a in listing_articles if a.get("id") == sid), None)

                metrics = score_article(
                    payload, level,
                    listing_summary=(listing_entry or {}).get("summary", ""),
                )
                if metrics["all_ok"]:
                    continue

                # Body word-count: queue for LLM rewrite if outside the
                # ±15% slack band. why_it_matters / listing-summary
                # overshoots are reported by the digest only — no
                # autofix action (mechanical trim leaves mid-thought
                # endings that ship to kids).
                lo, hi = BODY_TARGETS[level]
                hi_slack = hi * (1 + WC_SLACK)
                lo_slack = lo * (1 - WC_SLACK)
                if metrics["body_wc"] > hi_slack:
                    if not dry_run:
                        _enqueue(date_iso, sid, level, "body_too_long",
                                 {"wc": metrics["body_wc"], "target": metrics["body_target"]})
                    report["queued"].append({
                        "id": sid, "level": level, "type": "body_too_long",
                        "wc": metrics["body_wc"],
                    })
                elif metrics["body_wc"] < lo_slack:
                    if not dry_run:
                        _enqueue(date_iso, sid, level, "body_too_short",
                                 {"wc": metrics["body_wc"], "target": metrics["body_target"]})
                    report["queued"].append({
                        "id": sid, "level": level, "type": "body_too_short",
                        "wc": metrics["body_wc"],
                    })

                # keyword miss → queue (LLM weave or remove the term)
                if not metrics["kw_ok"] and metrics["kw_total"] > 0:
                    if not dry_run:
                        _enqueue(date_iso, sid, level, "keyword_miss",
                                 {"missed": metrics["kw_misses"], "total": metrics["kw_total"]})
                    report["queued"].append({
                        "id": sid, "level": level, "type": "keyword_miss",
                        "missed": metrics["kw_misses"],
                    })

                # image missing → queue (image regen)
                if not metrics["image_ok"]:
                    if not dry_run:
                        _enqueue(date_iso, sid, level, "image_missing", {})
                    report["queued"].append({
                        "id": sid, "level": level, "type": "image_missing",
                    })

    return report


def run(days: int, dry_run: bool) -> dict:
    today = datetime.now(ET).date()
    targets = [(today - timedelta(days=i)).isoformat() for i in range(days)]
    log.info("autofix scanning %d ET days: %s (dry_run=%s)",
             days, targets, dry_run)
    overall = {"days": [], "totals": {"queued": 0, "skipped": 0}}
    for d in targets:
        report = autofix_day(d, dry_run)
        overall["days"].append(report)
        overall["totals"]["queued"]  += len(report["queued"])
        overall["totals"]["skipped"] += len(report["skipped"])
    log.info("autofix totals: %s", overall["totals"])
    return overall


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days", type=int, default=1)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    out = run(days=args.days, dry_run=args.dry_run)
    print(json.dumps(out, indent=2, default=str))
