"""Auto-fix quality issues found by `pipeline.quality_digest`.

Two-tier fix strategy (matches Plan C — see
docs/superpowers/specs/2026-04-29-quality-digest-email.md):

  - **Mechanical fixes** (this module, runs in GitHub Actions):
    body too long → trim to last full sentence within target.
    why_it_matters too long → trim. summary too long → trim.
    These are deterministic, no LLM calls, safe.

  - **Complex fixes** (queued for the local Mac daemon):
    body too short, keyword miss, source diversity, image missing.
    These need agent-level reasoning + LLM regen → write a row to
    `redesign_autofix_queue` and let the launchd daemon (running
    Copilot CLI) handle them.

Re-uploads payloads to Supabase Storage. Works against the same
schema quality_digest reads (per-story `summary` field IS the body).

Usage:
    python -m pipeline.quality_autofix --days 1
    python -m pipeline.quality_autofix --days 1 --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib import error, parse, request
from zoneinfo import ZoneInfo

from pipeline.quality_digest import (
    ET, BODY_TARGETS, SUMMARY_MAX, WHY_MAX,
    LEVELS, CATS, STORAGE_BASE,
    score_article, gather_day, _fetch_json, _word_count,
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


def _upload_payload_json(date_iso: str, sub_path: str, obj: dict) -> bool:
    """Upload a JSON file to redesign-daily-content/<date>/<sub_path>.
    Uses upsert so the existing object is replaced cleanly."""
    url = f"{SUPABASE_URL}/storage/v1/object/redesign-daily-content/{date_iso}/{sub_path}"
    body = json.dumps(obj, ensure_ascii=False).encode()
    req = request.Request(
        url, method="PUT", data=body,
        headers={
            **_sb_headers(),
            "Content-Type": "application/json",
            # Storage's upload API expects this header on PUT replace.
            "x-upsert": "true",
            "cache-control": "no-cache",
        },
    )
    try:
        with request.urlopen(req, timeout=30) as r:
            return r.status in (200, 201)
    except error.HTTPError as e:
        log.error("upload %s failed: %s %s", url, e.code, e.read().decode()[:200])
        return False


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


# --- Mechanical trimmers -----------------------------------------

# Sentence end heuristic: ., !, ? followed by whitespace+capital
# letter or end-of-string. Designed to NOT chop mid-sentence.
_SENT_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z“‘(])")


def _trim_to_word_target(text: str, hi: int) -> str:
    """Cut `text` so the result is ≤ `hi` words, ending at a sentence
    boundary if possible. Falls back to word boundary if no sentence
    end is reachable."""
    words = text.split()
    if len(words) <= hi:
        return text
    # Walk the original text by characters, tracking word count, and
    # remember the latest sentence-end position before we exceed `hi`.
    word_idx = 0
    last_safe_pos = 0
    pos = 0
    for token in re.split(r"(\s+)", text):
        if not token.strip():
            pos += len(token)
            continue
        word_idx += 1
        pos += len(token)
        # Did this token end a sentence?
        if token and token[-1] in ".!?":
            if word_idx <= hi:
                last_safe_pos = pos
        if word_idx > hi:
            break
    if last_safe_pos > 0:
        return text[:last_safe_pos].rstrip()
    # No sentence boundary fit — fall back to word truncation.
    return " ".join(words[:hi]).rstrip(" ,;:") + "."


# --- Per-issue handlers ------------------------------------------

def _fix_body_too_long(payload: dict, level: str) -> tuple[bool, dict]:
    """Trim payload['summary'] (which IS the body) to target hi."""
    lo, hi = BODY_TARGETS[level]
    body = payload.get("summary") or ""
    new = _trim_to_word_target(body, hi)
    new_wc = _word_count(new)
    if new_wc < lo:
        # Trimming would push us BELOW target lo — leave it for the
        # complex queue (LLM rewrite needed).
        return (False, {"reason": "trim would underflow target",
                        "wc_before": _word_count(body),
                        "wc_after_trim": new_wc})
    payload["summary"] = new
    return (True, {"wc_before": _word_count(body), "wc_after": new_wc})


def _fix_why_too_long(payload: dict) -> tuple[bool, dict]:
    why = payload.get("why_it_matters") or ""
    new = _trim_to_word_target(why, WHY_MAX)
    payload["why_it_matters"] = new
    return (True, {"wc_before": _word_count(why),
                   "wc_after":  _word_count(new)})


def _fix_listing_summary_too_long(listing_entry: dict) -> tuple[bool, dict]:
    s = listing_entry.get("summary") or ""
    new = _trim_to_word_target(s, SUMMARY_MAX)
    listing_entry["summary"] = new
    return (True, {"wc_before": _word_count(s),
                   "wc_after":  _word_count(new)})


# --- Orchestration -----------------------------------------------

def autofix_day(date_iso: str, dry_run: bool) -> dict:
    """Read one day's content, mechanically fix what we can, queue
    what we can't. Returns a per-day report dict."""
    report: dict[str, Any] = {
        "date": date_iso,
        "fixed_mechanical": [],
        "queued": [],
        "skipped": [],
    }

    for cat in CATS:
        # Pull listings (need them to find story IDs and to fix
        # listing-level summaries).
        listings: dict[str, dict] = {}
        for level in LEVELS:
            url = f"{STORAGE_BASE}/{date_iso}/payloads/articles_{cat}_{level}.json"
            listings[level] = _fetch_json(url) or {}
        easy_articles = listings.get("easy", {}).get("articles", [])
        story_ids = [a["id"] for a in easy_articles[:3]]

        # Track which listings we mutate so we upload them once at the end.
        mutated_listings: set[str] = set()

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

                payload_changed = False
                listing_changed = False
                fixes: list[dict] = []

                # 1. body too long → mechanical trim
                lo, hi = BODY_TARGETS[level]
                if metrics["body_wc"] > hi:
                    ok, detail = _fix_body_too_long(payload, level)
                    if ok:
                        payload_changed = True
                        fixes.append({"type": "body_trim", **detail})
                    else:
                        # Trim would underflow → escalate as too-short.
                        if not dry_run:
                            _enqueue(date_iso, sid, level, "body_too_long",
                                     {"wc": metrics["body_wc"], "target": metrics["body_target"], **detail})
                        report["queued"].append({
                            "id": sid, "level": level, "type": "body_too_long",
                            "detail": detail,
                        })

                # 2. body too short → can't mechanically fix → queue
                if metrics["body_wc"] < lo:
                    if not dry_run:
                        _enqueue(date_iso, sid, level, "body_too_short",
                                 {"wc": metrics["body_wc"], "target": metrics["body_target"]})
                    report["queued"].append({
                        "id": sid, "level": level, "type": "body_too_short",
                        "wc": metrics["body_wc"],
                    })

                # 3. why too long → mechanical trim
                if not metrics["why_ok"]:
                    ok, detail = _fix_why_too_long(payload)
                    if ok:
                        payload_changed = True
                        fixes.append({"type": "why_trim", **detail})

                # 4. summary (listing) too long → mechanical trim
                if not metrics["summary_ok"] and listing_entry:
                    ok, detail = _fix_listing_summary_too_long(listing_entry)
                    if ok:
                        listing_changed = True
                        mutated_listings.add(level)
                        fixes.append({"type": "summary_trim", **detail})

                # 5. keyword miss → can't mechanically fix → queue
                if not metrics["kw_ok"] and metrics["kw_total"] > 0:
                    if not dry_run:
                        _enqueue(date_iso, sid, level, "keyword_miss",
                                 {"missed": metrics["kw_misses"], "total": metrics["kw_total"]})
                    report["queued"].append({
                        "id": sid, "level": level, "type": "keyword_miss",
                        "missed": metrics["kw_misses"],
                    })

                # 6. image missing → queue (re-gen needed)
                if not metrics["image_ok"]:
                    if not dry_run:
                        _enqueue(date_iso, sid, level, "image_missing", {})
                    report["queued"].append({
                        "id": sid, "level": level, "type": "image_missing",
                    })

                if fixes and not dry_run and payload_changed:
                    if _upload_payload_json(date_iso, payload_url_path, payload):
                        report["fixed_mechanical"].append({
                            "id": sid, "level": level, "fixes": fixes,
                        })
                    else:
                        log.error("upload failed for %s/%s — fix lost", sid, level)
                elif fixes and dry_run:
                    report["fixed_mechanical"].append({
                        "id": sid, "level": level, "fixes": fixes, "dry_run": True,
                    })

        # Upload mutated listings (after all stories in the cat).
        for level in mutated_listings:
            if not dry_run:
                listing_path = f"payloads/articles_{cat}_{level}.json"
                _upload_payload_json(date_iso, listing_path, listings[level])

    return report


def run(days: int, dry_run: bool) -> dict:
    today = datetime.now(ET).date()
    targets = [(today - timedelta(days=i)).isoformat() for i in range(days)]
    log.info("autofix scanning %d ET days: %s (dry_run=%s)",
             days, targets, dry_run)
    overall = {"days": [], "totals": {"fixed": 0, "queued": 0, "skipped": 0}}
    for d in targets:
        report = autofix_day(d, dry_run)
        overall["days"].append(report)
        overall["totals"]["fixed"]   += len(report["fixed_mechanical"])
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
