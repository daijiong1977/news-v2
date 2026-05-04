"""Apply auto-fixes to queued quality issues, in-process.

Routine word-count / keyword / image fixes are handled here directly:
DeepSeek (text-shape transforms) or the og:image extractor (image
regrab). No agent needed for the routine 80%.

Per the project policy:
  body_too_long / body_too_short  → ONE DeepSeek regen attempt, accept
                                    whatever comes back, log final wc
  keyword_miss                    → ONE DeepSeek attempt: weave the
                                    keyword OR drop it if it's a junk
                                    artifact
  image_missing                   → up to TWO image-regrab attempts via
                                    og:image (different fetch headers
                                    each try)
  anything else / LLM fail        → mark row 'escalated'; the local
                                    Claude Code scheduled task picks it
                                    up at the next 3am / 10am fire and
                                    runs the kidsnews-bugfix skill.
                                    See docs/AUTOFIX-SCHEDULED-TASK.md.

Runs from .github/workflows/quality-digest.yml between
`pipeline.quality_autofix` (which enqueues) and `pipeline.quality_digest`
(which reports).

Usage:
    python -m pipeline.autofix_apply --max 20
    python -m pipeline.autofix_apply --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any
from urllib import error, request

from pipeline.quality_digest import (
    BODY_TARGETS, WC_SLACK, _fetch_json, _word_count,
)
from pipeline.feedback_triage import _deepseek_call

log = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
STORAGE_BASE = f"{SUPABASE_URL}/storage/v1/object/public/redesign-daily-content"


# ── HTTP / Storage helpers ───────────────────────────────────────

def _sb_headers() -> dict:
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}


def _upload_payload_json(date_iso: str, sub_path: str, obj: dict) -> bool:
    url = f"{SUPABASE_URL}/storage/v1/object/redesign-daily-content/{date_iso}/{sub_path}"
    body = json.dumps(obj, ensure_ascii=False).encode()
    req = request.Request(
        url, method="PUT", data=body,
        headers={**_sb_headers(), "Content-Type": "application/json",
                 "x-upsert": "true", "cache-control": "no-cache"},
    )
    try:
        with request.urlopen(req, timeout=30) as r:
            return r.status in (200, 201)
    except error.HTTPError as e:
        log.error("upload %s failed: %s %s", url, e.code, e.read().decode()[:200])
        return False


def _patch_row(row_id: int, fields: dict) -> None:
    body = json.dumps(fields).encode()
    req = request.Request(
        f"{SUPABASE_URL}/rest/v1/redesign_autofix_queue?id=eq.{row_id}",
        method="PATCH", data=body,
        headers={**_sb_headers(),
                 "Content-Type": "application/json",
                 "Prefer": "return=minimal"},
    )
    try:
        with request.urlopen(req, timeout=15) as r:
            r.read()
    except error.HTTPError as e:
        log.error("patch row %d failed: %s %s",
                  row_id, e.code, e.read().decode()[:200])


def _fetch_queued_rows(limit: int) -> list[dict]:
    url = (f"{SUPABASE_URL}/rest/v1/redesign_autofix_queue"
           f"?status=eq.queued&order=id.asc&limit={limit}")
    req = request.Request(url, headers=_sb_headers())
    with request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


# ── Per problem_type handlers ───────────────────────────────────

def _payload_url(date_iso: str, sid: str, level: str) -> tuple[str, str]:
    sub = f"article_payloads/payload_{sid}/{level}.json"
    return f"{STORAGE_BASE}/{date_iso}/{sub}", sub


_BODY_REWRITE_SYSTEM = """You rewrite kid-friendly news article bodies.

Hard rules:
- Output JSON ONLY: {"body": "<rewritten article body>"}
- Preserve every keyword listed in the input — each one must remain
  findable in your output (case-insensitive, word-boundary).
- Match the requested word count target (you have ±15% slack).
- Keep the same facts, names, dates. Do NOT invent details.
- Voice: warm, age-appropriate (8-12 year olds), short sentences.
- No headings, no bullet lists — flowing paragraphs only.
"""


def _fix_body(payload: dict, level: str, target_lo: int, target_hi: int,
              direction: str) -> tuple[bool, str, dict]:
    """One DeepSeek attempt to rewrite payload['summary'] (the body) into
    the target range. Returns (ok, summary_msg, detail)."""
    body = payload.get("summary") or ""
    keyword_terms = [
        (k.get("term") if isinstance(k, dict) else str(k))
        for k in (payload.get("keywords") or [])
    ]
    keyword_terms = [k for k in keyword_terms if k]

    user_prompt = (
        f"Rewrite this article body to be {target_lo}-{target_hi} words "
        f"(±15% slack OK).\n"
        f"Direction: it was previously TOO {direction.upper()} "
        f"({_word_count(body)} words).\n\n"
        f"Keywords (must all stay findable in the body):\n"
        + "\n".join(f"- {k}" for k in keyword_terms) + "\n\n"
        f"Original body:\n{body}\n"
    )
    try:
        out = _deepseek_call(_BODY_REWRITE_SYSTEM, user_prompt, max_tokens=1400)
    except Exception as e:
        return (False, f"DeepSeek call failed: {e}", {"error": str(e)})

    new_body = (out.get("body") or "").strip()
    if not new_body:
        return (False, "DeepSeek returned empty body", {"raw": str(out)[:200]})

    # Soft check — even if it's still off, we accept (per policy).
    new_wc = _word_count(new_body)
    payload["summary"] = new_body
    return (True,
            f"body rewritten: {_word_count(body)} → {new_wc} words "
            f"(target {target_lo}-{target_hi})",
            {"wc_before": _word_count(body), "wc_after": new_wc,
             "in_target": target_lo * (1 - WC_SLACK) <= new_wc <= target_hi * (1 + WC_SLACK)})


_KEYWORD_FIX_SYSTEM = """You fix keyword-coverage issues in kid news article bodies.

Decide: is each "missed keyword" a real concept the body should mention,
or is it a junk LLM artifact (random preposition, fragment like "A final")?

Output JSON ONLY:
  {"action": "weave",  "body": "<rewritten body>"}
  OR
  {"action": "drop",   "drop_terms": ["term1", "term2"]}

Rules for weave:
- Add every missed keyword findable in the new body (case-insensitive,
  word-boundary). One natural sentence per term.
- Keep the same facts, voice, tone. Do not exceed +15% of the original
  word count.

Rules for drop:
- Use ONLY when the missed keyword is obviously not a real concept.
- List exactly the terms to remove from the keywords array.
"""


def _fix_keyword(payload: dict, missed: list[str]) -> tuple[bool, str, dict]:
    body = payload.get("summary") or ""
    user_prompt = (
        f"Missed keyword(s) (not currently findable in body): {missed}\n"
        f"Body:\n{body}\n"
    )
    try:
        out = _deepseek_call(_KEYWORD_FIX_SYSTEM, user_prompt, max_tokens=1400)
    except Exception as e:
        return (False, f"DeepSeek call failed: {e}", {"error": str(e)})

    action = (out.get("action") or "").strip().lower()
    if action == "weave":
        new_body = (out.get("body") or "").strip()
        if not new_body:
            return (False, "weave returned empty body", {})
        payload["summary"] = new_body
        return (True, f"wove {len(missed)} keyword(s) into body",
                {"action": "weave", "wc_after": _word_count(new_body)})
    if action == "drop":
        drops = [str(t).lower() for t in (out.get("drop_terms") or [])]
        kept = []
        removed: list[str] = []
        for k in (payload.get("keywords") or []):
            term = (k.get("term") if isinstance(k, dict) else str(k)) or ""
            if term.lower() in drops:
                removed.append(term)
            else:
                kept.append(k)
        payload["keywords"] = kept
        return (True, f"dropped {len(removed)} junk keyword(s): {removed}",
                {"action": "drop", "removed": removed})
    return (False, f"unrecognised action: {action!r}", {"raw": str(out)[:200]})


_HEADERS_TRY_1 = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/130.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml",
}
_HEADERS_TRY_2 = {
    "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "Accept": "text/html",
}


def _try_extract_og_image(article_url: str, headers: dict) -> str | None:
    """One attempt to fetch article_url and pull og:image. Returns None
    on failure (we'll try again with different headers if any)."""
    try:
        req = request.Request(article_url, headers=headers)
        with request.urlopen(req, timeout=20) as r:
            html = r.read(800_000).decode("utf-8", errors="ignore")
    except Exception as e:
        log.warning("image fetch %s failed: %s", article_url[:80], e)
        return None
    # Cheap regex over the og:image meta — avoids pulling BeautifulSoup
    # in if not already imported. The pipeline normalises later.
    import re
    for pattern in (
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
    ):
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _fix_image(payload: dict) -> tuple[bool, str, dict]:
    article_url = (payload.get("source_url") or payload.get("url") or "").strip()
    if not article_url:
        return (False, "no source_url on payload — can't regrab",
                {"reason": "missing_source_url"})
    for attempt, headers in enumerate((_HEADERS_TRY_1, _HEADERS_TRY_2), start=1):
        img = _try_extract_og_image(article_url, headers)
        if img:
            payload["image_url"] = img
            return (True, f"regrabbed og:image on attempt {attempt}",
                    {"attempt": attempt, "image_url": img})
    return (False, "og:image not found on 2 attempts",
            {"attempts": 2})


# ── Orchestration ───────────────────────────────────────────────

def _resolve(row: dict, msg: str, detail: dict) -> dict:
    _patch_row(row["id"], {
        "status": "resolved",
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "agent_log": json.dumps({"resolved_msg": msg, "detail": detail})[:7000],
    })
    return {"id": row["id"], "outcome": "resolved", "msg": msg}


def _escalate(row: dict, msg: str, detail: dict) -> dict:
    _patch_row(row["id"], {
        "status": "escalated",
        "agent_log": json.dumps({"escalated_msg": msg, "detail": detail})[:7000],
    })
    return {"id": row["id"], "outcome": "escalated", "msg": msg}


def process_row(row: dict, dry_run: bool) -> dict:
    """Apply the appropriate fix in-process. Returns a result dict."""
    rid    = row["id"]
    pdate  = row["published_date"]
    sid    = row["story_id"]
    level  = row["level"]
    ptype  = row["problem_type"]
    detail = row.get("problem_detail") or {}

    log.info("[row %d] %s %s/%s %s", rid, pdate, sid, level, ptype)

    if dry_run:
        return {"id": rid, "outcome": "dry_run", "type": ptype}

    # Mark running and bump attempts
    _patch_row(rid, {
        "status": "running",
        "last_attempt_at": datetime.now(timezone.utc).isoformat(),
        "attempts": (row.get("attempts") or 0) + 1,
    })

    full_url, sub_path = _payload_url(pdate, sid, level)
    payload = _fetch_json(full_url)
    if not payload:
        return _escalate(row, "payload not found at Storage", {"url": full_url})

    if ptype in ("body_too_long", "body_too_short"):
        if level not in BODY_TARGETS:
            return _escalate(row, f"unknown level {level!r}", {})
        lo, hi = BODY_TARGETS[level]
        direction = "long" if ptype == "body_too_long" else "short"
        ok, msg, det = _fix_body(payload, level, lo, hi, direction)
        if not ok:
            return _escalate(row, msg, det)
        if not _upload_payload_json(pdate, sub_path, payload):
            return _escalate(row, "Storage upload failed after rewrite",
                             {"sub_path": sub_path, **det})
        return _resolve(row, msg, det)

    if ptype == "keyword_miss":
        missed = detail.get("missed") or []
        if not missed:
            return _escalate(row, "keyword_miss row has no 'missed' list", detail)
        ok, msg, det = _fix_keyword(payload, missed)
        if not ok:
            return _escalate(row, msg, det)
        if not _upload_payload_json(pdate, sub_path, payload):
            return _escalate(row, "Storage upload failed after keyword fix",
                             {"sub_path": sub_path, **det})
        return _resolve(row, msg, det)

    if ptype == "image_missing":
        ok, msg, det = _fix_image(payload)
        if not ok:
            return _escalate(row, msg, det)
        if not _upload_payload_json(pdate, sub_path, payload):
            return _escalate(row, "Storage upload failed after image regrab",
                             {"sub_path": sub_path, **det})
        return _resolve(row, msg, det)

    return _escalate(row, f"unknown problem_type {ptype!r}", {})


def run(max_rows: int, dry_run: bool) -> dict:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY required")
    rows = _fetch_queued_rows(max_rows)
    log.info("found %d queued row(s)", len(rows))
    results: list[dict] = []
    for row in rows:
        try:
            results.append(process_row(row, dry_run=dry_run))
        except Exception as e:
            log.exception("row %d crashed: %s", row.get("id"), e)
            results.append({"id": row.get("id"), "outcome": "escalated",
                            "msg": f"unhandled exception: {e}"})
            if not dry_run:
                _patch_row(row["id"], {
                    "status": "escalated",
                    "agent_log": json.dumps({
                        "escalated_msg": "unhandled exception",
                        "exception": str(e)[:500],
                    })[:7000],
                })
    summary = {
        "total":      len(results),
        "resolved":   sum(1 for r in results if r["outcome"] == "resolved"),
        "escalated":  sum(1 for r in results if r["outcome"] == "escalated"),
        "dry_run":    dry_run,
        "results":    results,
    }
    log.info("autofix_apply summary: %s",
             {k: v for k, v in summary.items() if k != "results"})
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--max", type=int, default=20, dest="max_rows",
                   help="Max queued rows to process this run")
    p.add_argument("--dry-run", action="store_true",
                   help="Skip mutations, just report what would happen")
    args = p.parse_args()
    out = run(max_rows=args.max_rows, dry_run=args.dry_run)
    print(json.dumps(out, indent=2, default=str))
