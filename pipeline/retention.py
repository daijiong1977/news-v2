"""Retention cleanup — delete pipeline-generated content older than
`engine_config['retention.days']`. User data (reactions, responses,
quiz attempts, kid profiles, parent users, etc.) is NEVER touched.

Tables purged (by published_date or run_date or created_at):
  · redesign_stories
  · redesign_runs
  · redesign_checkpoints
  · redesign_search_index
  · engine_source_daily_stats        (sourcefinder; same retention applies)

Storage purged:
  · redesign-daily-content/<date>/...  for every <date> older than cutoff
  · redesign-article-images/<date>/... same

Usage:
    python -m pipeline.retention                    # honors engine_config['retention.days']
    python -m pipeline.retention --days 14          # one-off override
    python -m pipeline.retention --dry-run          # show what would be deleted
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib import error, request

log = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")


def _h() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def _http(method: str, url: str, body=None) -> tuple[int, str]:
    req = request.Request(
        url, method=method, headers=_h(),
        data=json.dumps(body).encode() if body is not None else None,
    )
    try:
        with request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def _read_retention_days() -> int:
    """engine_config['retention.days'] is a JSON int. Default 30."""
    code, body = _http(
        "GET",
        f"{SUPABASE_URL}/rest/v1/engine_config?key=eq.retention.days&select=value",
    )
    if code != 200:
        log.warning("could not read engine_config[retention.days]: %s", code)
        return 30
    rows = json.loads(body)
    if not rows:
        return 30
    try:
        return int(rows[0]["value"])
    except (KeyError, ValueError, TypeError):
        return 30


def _delete_rows(table: str, query: str, dry_run: bool) -> int:
    """DELETE FROM <table> WHERE <query>. Returns count."""
    # First count
    code, body = _http(
        "GET",
        f"{SUPABASE_URL}/rest/v1/{table}?select=count&{query}",
    )
    if code != 200:
        log.warning("count %s failed: %s", table, code)
        return 0
    # PostgREST returns [{"count": N}] when select=count is used? Actually
    # the proper way is to use Prefer: count=exact and read the
    # Content-Range header. Skip that — use a simple LIMIT 0 trick is
    # noisy. Easiest: just DELETE and ask for return=representation
    # (counts the affected rows).
    if dry_run:
        # Read up to 5 rows to show what would die
        code2, body2 = _http(
            "GET",
            f"{SUPABASE_URL}/rest/v1/{table}?select=*&{query}&limit=5",
        )
        rows = json.loads(body2) if code2 == 200 else []
        log.info("DRY RUN %s WHERE %s — sample: %s",
                 table, query, [r.get("id") or r.get("run_date") or r.get("published_date") for r in rows])
        return len(rows)

    # Real delete
    req = request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}?{query}",
        method="DELETE",
        headers={**_h(), "Prefer": "return=representation"},
    )
    try:
        with request.urlopen(req, timeout=60) as r:
            data = r.read().decode()
    except error.HTTPError as e:
        log.error("delete %s failed: %s — %s", table, e.code, e.read().decode()[:300])
        return 0
    try:
        rows = json.loads(data)
        return len(rows)
    except Exception:
        return 0


def _list_storage_dates(bucket: str) -> list[str]:
    """List top-level YYYY-MM-DD folders in a bucket."""
    req = request.Request(
        f"{SUPABASE_URL}/storage/v1/object/list/{bucket}",
        method="POST",
        headers=_h(),
        data=json.dumps({"prefix": "", "limit": 1000,
                         "sortBy": {"column": "name", "order": "asc"}}).encode(),
    )
    try:
        with request.urlopen(req, timeout=30) as r:
            entries = json.loads(r.read())
    except error.HTTPError as e:
        log.warning("list bucket %s: %s", bucket, e.code)
        return []
    dates = []
    for e in entries:
        n = e.get("name", "")
        if len(n) == 10 and n[4] == '-' and n[7] == '-' and n.replace('-', '').isdigit():
            dates.append(n)
    return sorted(dates)


def _list_storage_paths_under(bucket: str, prefix: str) -> list[str]:
    """Recursively list all object paths under prefix/."""
    out: list[str] = []
    stack = [prefix]
    while stack:
        cur = stack.pop()
        req = request.Request(
            f"{SUPABASE_URL}/storage/v1/object/list/{bucket}",
            method="POST",
            headers=_h(),
            data=json.dumps({"prefix": cur, "limit": 1000,
                             "sortBy": {"column": "name", "order": "asc"}}).encode(),
        )
        try:
            with request.urlopen(req, timeout=30) as r:
                entries = json.loads(r.read())
        except error.HTTPError:
            continue
        for e in entries:
            name = e.get("name", "")
            full = f"{cur}/{name}" if cur and not cur.endswith('/') else cur + name
            if e.get("id"):
                out.append(full)
            else:
                # subdirectory
                stack.append(full + "/")
    return out


def _delete_storage_paths(bucket: str, paths: list[str], dry_run: bool) -> int:
    """Bulk-delete object paths in a bucket. Returns count successfully removed."""
    if not paths:
        return 0
    if dry_run:
        log.info("DRY RUN delete %d objects from %s — sample: %s",
                 len(paths), bucket, paths[:5])
        return len(paths)
    deleted = 0
    for i in range(0, len(paths), 200):
        batch = paths[i:i + 200]
        req = request.Request(
            f"{SUPABASE_URL}/storage/v1/object/{bucket}",
            method="DELETE",
            headers=_h(),
            data=json.dumps({"prefixes": batch}).encode(),
        )
        try:
            with request.urlopen(req, timeout=60) as r:
                _ = r.read()
            deleted += len(batch)
        except error.HTTPError as e:
            log.warning("delete batch %d of %s failed: %s", i // 200, bucket, e.code)
    return deleted


def cleanup(days: int | None = None, dry_run: bool = False) -> dict:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
    if days is None:
        days = _read_retention_days()
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()
    log.info("retention cutoff = %s (%d days)", cutoff_iso, days)
    summary: dict[str, int] = {}

    # Tables — pipeline-generated only.
    summary["redesign_stories"] = _delete_rows(
        "redesign_stories", f"published_date=lt.{cutoff_iso}", dry_run
    )
    summary["redesign_runs"] = _delete_rows(
        "redesign_runs", f"run_date=lt.{cutoff_iso}", dry_run
    )
    summary["redesign_checkpoints"] = _delete_rows(
        "redesign_checkpoints", f"run_date=lt.{cutoff_iso}", dry_run
    )
    summary["redesign_search_index"] = _delete_rows(
        "redesign_search_index", f"published_date=lt.{cutoff_iso}", dry_run
    )
    summary["engine_source_daily_stats"] = _delete_rows(
        "engine_source_daily_stats", f"run_date=lt.{cutoff_iso}", dry_run
    )

    # Storage — only the dated directories.
    for bucket in ("redesign-daily-content", "redesign-article-images"):
        old_dates = [d for d in _list_storage_dates(bucket) if d < cutoff_iso]
        if not old_dates:
            summary[f"{bucket}_paths"] = 0
            continue
        all_paths: list[str] = []
        for d in old_dates:
            all_paths.extend(_list_storage_paths_under(bucket, d + "/"))
        summary[f"{bucket}_paths"] = _delete_storage_paths(bucket, all_paths, dry_run)

    log.info("retention cleanup done: %s", summary)
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                         format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days", type=int, default=None,
                   help="Override retention.days (default: read from engine_config)")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would be deleted, don't actually delete")
    args = p.parse_args()
    summary = cleanup(days=args.days, dry_run=args.dry_run)
    print(json.dumps(summary, indent=2))
