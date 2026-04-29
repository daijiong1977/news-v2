"""Maintain redesign_search_index — one row per (story_id, level).

Two entry points:
  · upsert_one(story_id, level, payload) — pipeline calls this after
    pack_and_upload writes a payload, so search lights up the moment
    today's bundle is live.
  · backfill(days=30) — one-shot. Walks the Supabase storage layout,
    pulls each `<date>/article_payloads/payload_<id>/<level>.json`,
    and indexes everything in the window. Idempotent (UNIQUE (story_id,
    level) on the table).
"""
from __future__ import annotations

import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from urllib import error, request

log = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
STORAGE_BASE = f"{SUPABASE_URL}/storage/v1/object/public/redesign-daily-content"
REST_BASE = f"{SUPABASE_URL}/rest/v1"

CATS = ("News", "Science", "Fun")
LEVELS = ("easy", "middle", "zh")


def _headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def _post(path: str, body) -> tuple[int, str]:
    req = request.Request(
        f"{REST_BASE}{path}",
        method="POST",
        headers={**_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
        data=json.dumps(body).encode(),
    )
    try:
        with request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def _fetch_json(url: str) -> dict | None:
    try:
        with request.urlopen(url, timeout=15) as r:
            return json.loads(r.read())
    except (error.HTTPError, error.URLError):
        return None


def _to_row(story_id: str, published_date: str, category: str,
             level: str, payload: dict) -> dict:
    """Map one payload JSON into a redesign_search_index row."""
    if level not in ("easy", "middle"):
        # zh payload uses different shape; keep level marker but
        # title/summary still works.
        pass
    keywords_field = payload.get("keywords") or []
    # keywords is a list of {"term", "explanation"} dicts in the v1
    # payload — flatten to terms only.
    if keywords_field and isinstance(keywords_field[0], dict):
        keyword_terms = [k.get("term") for k in keywords_field if k.get("term")]
    else:
        keyword_terms = [str(k) for k in keywords_field]
    return {
        "story_id": story_id,
        "published_date": published_date,
        "category": category,
        "level": level,
        "title": payload.get("title", ""),
        "summary": payload.get("summary", ""),
        "why": payload.get("why_it_matters", ""),
        "keywords": keyword_terms,
        "image_url": payload.get("image_url", ""),
        "source_name": payload.get("source_name", ""),
    }


def upsert_rows(rows: list[dict]) -> int:
    """Bulk upsert into redesign_search_index. Returns count."""
    if not rows:
        return 0
    code, _ = _post(
        "/redesign_search_index?on_conflict=story_id,level",
        rows,
    )
    if code not in (200, 201, 204):
        log.warning("upsert returned %s", code)
        return 0
    return len(rows)


def upsert_one(story_id: str, published_date: str, category: str,
                level: str, payload: dict) -> bool:
    """Index a single payload. Use from pack_and_upload."""
    row = _to_row(story_id, published_date, category, level, payload)
    return upsert_rows([row]) == 1


def _walk_one_day(d: date) -> list[dict]:
    """For one date, read the listing JSONs to get story IDs, then
    fetch each story's payload JSONs to build search rows."""
    rows: list[dict] = []
    iso = d.isoformat()
    listings_base = f"{STORAGE_BASE}/{iso}/payloads"
    for cat in CATS:
        cat_lc = cat.lower()
        # easy/middle/cn listings each have the top-3 stories for that
        # category. We fetch easy to get the canonical 3 story IDs +
        # categories, then pull each story's per-level payload.
        listing = _fetch_json(f"{listings_base}/articles_{cat_lc}_easy.json")
        if not listing:
            continue
        story_ids = [a["id"] for a in (listing.get("articles") or [])[:3]]
        for sid in story_ids:
            for level in LEVELS:
                # zh payload stored as `cn` per existing convention
                level_path = "cn" if level == "zh" else level
                url = f"{STORAGE_BASE}/{iso}/article_payloads/payload_{sid}/{level_path}.json"
                p = _fetch_json(url)
                if p:
                    rows.append(_to_row(sid, iso, cat, level, p))
    return rows


def backfill(days: int = 30) -> int:
    """Backfill the last N days from Supabase storage. Idempotent."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
        return 0
    today = datetime.now(timezone.utc).date()
    targets = [today - timedelta(days=i) for i in range(days + 1)]
    total = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        for rows in ex.map(_walk_one_day, targets):
            if rows:
                n = upsert_rows(rows)
                total += n
                log.info("indexed %d rows for %s", n, rows[0]["published_date"])
    return total


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO,
                         format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=30,
                   help="Backfill the last N days (default 30)")
    args = p.parse_args()
    n = backfill(args.days)
    print(f"backfilled {n} rows")
