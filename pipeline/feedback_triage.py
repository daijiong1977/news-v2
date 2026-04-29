"""Auto-triage user feedback rows.

Daily cron reads `redesign_feedback` rows with `triaged_status='new'`,
classifies each via DeepSeek, opens a GitHub issue per non-noise row,
and writes the issue URL + classification back to the DB. Humans still
do the final 'convert to bug record' step in admin — this module only
does the cognitive work (classify, summarize, suggest slug, dedup).

Output classifications:
  - bug:        a real defect; attach LLM-suggested severity + slug
  - suggestion: feature request, UX nit
  - content:    article-level feedback (boring story, factual issue)
  - noise:      spam / unintelligible / not actionable → auto-dismiss
  - duplicate:  near-duplicate of an already-open issue → auto-link

Usage:
    python -m pipeline.feedback_triage
    python -m pipeline.feedback_triage --dry-run        # don't open issues, don't write DB
    python -m pipeline.feedback_triage --since-hours 48 # default 48
    python -m pipeline.feedback_triage --max 50         # cap per-run cost
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import error, parse, request

log = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = os.environ.get("DEEPSEEK_ENDPOINT", "https://api.deepseek.com/chat/completions")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL_TRIAGE", "deepseek-v4-flash")
GH_TOKEN     = os.environ.get("GITHUB_TOKEN", "")
GH_REPO      = os.environ.get("GH_REPO", "daijiong1977/news-v2")  # owner/name


def _deepseek_call(system: str, user: str, max_tokens: int = 800) -> dict:
    """Inline DeepSeek call — same provider as the rewrite/curator
    pipeline but without the news_rss_core dependency tree (which
    pulls in feedparser etc. that triage doesn't need)."""
    if not DEEPSEEK_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY not set")
    payload = json.dumps({
        "model": DEEPSEEK_MODEL,
        "thinking": {"type": "disabled"},
        "messages": [{"role": "system", "content": system},
                     {"role": "user",   "content": user}],
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }).encode()
    req = request.Request(
        DEEPSEEK_URL, method="POST", data=payload,
        headers={
            "Authorization": f"Bearer {DEEPSEEK_KEY}",
            "Content-Type": "application/json",
        },
    )
    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            with request.urlopen(req, timeout=60) as r:
                body = r.read().decode()
            data = json.loads(body)
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as e:
            last_err = e
            log.warning("deepseek call attempt %d failed: %s", attempt, e)
            if attempt < 3:
                import time
                time.sleep(2 * attempt)
    raise RuntimeError(f"deepseek_call exhausted 3 attempts") from last_err


SYSTEM_PROMPT = """You triage user feedback for a kids-news website.

Output JSON ONLY, no prose, with this exact shape:

{
  "classification": "bug" | "suggestion" | "content" | "noise" | "duplicate",
  "severity": "low" | "medium" | "high" | "critical" | null,
  "summary": "<one short sentence — 80 chars max — describing the symptom>",
  "slug": "<kebab-case slug, 4-6 words, suitable for docs/bugs/<date>-<slug>.md>",
  "rationale": "<one sentence explaining the classification>",
  "is_actionable": true | false
}

Rules:
- "bug": something is broken, returns wrong result, crashes, looks
  obviously wrong (e.g. "doesn't load", "shows wrong article",
  "button does nothing"). severity required.
- "suggestion": feature request or UX improvement. severity null.
- "content": complaint about a specific article — boring, factually
  off, too hard, too easy. severity = "low" unless factual error.
- "noise": spam, gibberish, untestable vague complaints with zero
  signal ("bad", "ok", "asdf"), profanity-only. severity null.
  is_actionable=false.
- "duplicate": ONLY if the message clearly references a known issue
  already open. (You do not have access to issue history — only mark
  duplicate if the user explicitly says so.)
- severity for bugs:
    critical = data loss / total outage / security
    high     = main feature broken
    medium   = secondary feature broken / wrong content for many users
    low      = minor visual glitch / single-user edge case
- The slug must be kebab-case ASCII, e.g. "search-button-mobile-overlap".

Be strict — when uncertain between bug and suggestion, pick suggestion.
Between suggestion and noise, pick noise only if there's truly zero signal."""


def _http(method: str, url: str, headers: dict | None = None,
           body: bytes | None = None, timeout: int = 30) -> tuple[int, str]:
    req = request.Request(url, method=method,
                           headers=headers or {}, data=body)
    try:
        with request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except error.HTTPError as e:
        return e.code, e.read().decode()[:1000]


def _sb_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def _gh_headers() -> dict:
    return {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }


def fetch_new_feedback(since_hours: int, limit: int) -> list[dict]:
    """Pull untriaged rows."""
    since = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()
    q = parse.urlencode({
        "select": "*",
        "triaged_status": "eq.new",
        "triage_at": "is.null",   # never triaged before
        "created_at": f"gte.{since}",
        "order": "created_at.asc",
        "limit": str(limit),
    })
    code, body = _http(
        "GET", f"{SUPABASE_URL}/rest/v1/redesign_feedback?{q}",
        headers=_sb_headers(),
    )
    if code != 200:
        raise RuntimeError(f"fetch_new_feedback failed: {code} {body[:200]}")
    return json.loads(body)


def update_feedback(row_id: int, patch: dict) -> bool:
    body = json.dumps(patch).encode()
    code, resp = _http(
        "PATCH", f"{SUPABASE_URL}/rest/v1/redesign_feedback?id=eq.{row_id}",
        headers={**_sb_headers(), "Prefer": "return=minimal"},
        body=body,
    )
    if code not in (200, 204):
        log.warning("update_feedback %d failed: %s %s", row_id, code, resp[:200])
        return False
    return True


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:60] or "feedback"


def classify(row: dict) -> dict:
    """Send the row through DeepSeek and return the parsed classification.
    On any error, returns a 'noise' fallback so downstream still runs."""
    user_msg = "\n".join([
        f"Submitted at: {row.get('created_at')}",
        f"Category (user-chosen): {row.get('category')}",
        f"User level: {row.get('user_level') or '—'}",
        f"User language: {row.get('user_language') or '—'}",
        f"Page URL: {row.get('page_url') or '—'}",
        "",
        "Message:",
        row.get("message") or "",
    ])
    try:
        out = _deepseek_call(SYSTEM_PROMPT, user_msg, max_tokens=600)
    except Exception as e:
        log.warning("classify row %s failed: %s", row.get("id"), e)
        return {
            "classification": "noise",
            "severity": None,
            "summary": (row.get("message") or "")[:80],
            "slug": "unparseable",
            "rationale": f"LLM call failed: {e}",
            "is_actionable": False,
        }
    # Defensive sanity-check the output shape.
    cls = out.get("classification")
    if cls not in ("bug", "suggestion", "content", "noise", "duplicate"):
        out["classification"] = "noise"
        out["rationale"] = f"unexpected classification '{cls}'; demoted to noise"
    out["slug"] = slugify(str(out.get("slug") or "feedback"))
    out["summary"] = str(out.get("summary") or "")[:120]
    return out


def open_github_issue(row: dict, triage: dict) -> tuple[int | None, str | None]:
    """Open one issue per non-noise row. Returns (number, url)."""
    if not GH_TOKEN:
        log.warning("GITHUB_TOKEN not set; skipping issue creation")
        return (None, None)
    cls = triage["classification"]
    sev = triage.get("severity") or "—"
    label_map = {"bug": ["bug", "feedback"],
                 "suggestion": ["enhancement", "feedback"],
                 "content": ["content", "feedback"],
                 "duplicate": ["duplicate", "feedback"]}
    labels = label_map.get(cls, ["feedback"])
    title_prefix = {"bug": "🐞 BUG", "suggestion": "💡 SUG",
                    "content": "📰 CONT", "duplicate": "🔁 DUP"}[cls]
    title = f"{title_prefix}: {triage['summary']}"[:200]

    body_parts = [
        "_Auto-triaged from `redesign_feedback`._",
        "",
        f"**Classification:** `{cls}`",
        f"**Severity:** `{sev}`",
        f"**Suggested slug:** `{triage['slug']}`",
        f"**Rationale:** {triage.get('rationale','—')}",
        "",
        "---",
        "",
        "## Original message",
        "",
        f"> {row.get('message','').replace(chr(10), chr(10) + '> ')}",
        "",
        "## Context",
        "",
        f"- **Submitted:** {row.get('created_at')}",
        f"- **Category (user-chosen):** {row.get('category')}",
        f"- **User level:** {row.get('user_level') or '—'}",
        f"- **User language:** {row.get('user_language') or '—'}",
        f"- **Page URL:** {row.get('page_url') or '—'}",
        f"- **Client ID:** `{(row.get('client_id') or '')[:12]}…`",
        f"- **Feedback row ID:** `{row.get('id')}`",
        "",
        "## Next steps",
        "",
        "- [ ] Reproduce / verify",
        "- [ ] If bug: copy `docs/bugs/_template.md` → "
            f"`docs/bugs/{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{triage['slug']}.md`, "
            "fill in Symptom from above, add row to `INDEX.md`",
        "- [ ] In admin → 💬 Feedback, click '→ Bug record' on row "
            f"`#{row.get('id')}` and paste the path",
        "- [ ] Implement + commit with `Bug-Record:` trailer",
    ]

    payload = json.dumps({
        "title": title,
        "body": "\n".join(body_parts),
        "labels": labels,
    }).encode()

    code, resp = _http(
        "POST", f"https://api.github.com/repos/{GH_REPO}/issues",
        headers=_gh_headers(), body=payload, timeout=30,
    )
    if code not in (200, 201):
        log.warning("issue creation failed (%d): %s", code, resp[:200])
        return (None, None)
    obj = json.loads(resp)
    return (obj.get("number"), obj.get("html_url"))


def triage_one(row: dict, dry_run: bool) -> dict:
    """Classify one row + take action. Returns a result dict for digest."""
    triage = classify(row)
    cls = triage["classification"]
    result = {
        "id": row.get("id"),
        "msg_preview": (row.get("message") or "")[:80],
        "classification": cls,
        "severity": triage.get("severity"),
        "summary": triage.get("summary"),
        "slug": triage.get("slug"),
        "issue_url": None,
        "issue_number": None,
        "action": "",
    }

    if dry_run:
        result["action"] = f"DRY: would handle as {cls}"
        return result

    patch: dict[str, Any] = {
        "triage_classification": cls,
        "triage_severity": triage.get("severity"),
        "triage_summary": triage.get("summary"),
        "triage_slug": triage.get("slug"),
        "triage_at": datetime.now(timezone.utc).isoformat(),
    }

    if cls == "noise" or not triage.get("is_actionable", True):
        patch["triaged_status"] = "dismissed"
        patch["triaged_at"]    = datetime.now(timezone.utc).isoformat()
        patch["triaged_note"]  = f"auto-dismissed: {triage.get('rationale','')}"
        result["action"] = "auto-dismissed"
    else:
        # Open a GitHub issue. Leave triaged_status='new' so the user
        # still has to do the human convert step in admin.
        num, url = open_github_issue(row, triage)
        if url:
            patch["gh_issue_number"] = num
            patch["gh_issue_url"]    = url
            patch["triaged_note"]    = f"auto-triaged → {url}"
            result["issue_url"]      = url
            result["issue_number"]   = num
            result["action"]         = f"opened issue #{num}"
        else:
            result["action"] = "issue creation failed (see logs)"

    update_feedback(row["id"], patch)
    return result


def run(since_hours: int = 48, max_rows: int = 50, dry_run: bool = False) -> dict:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_KEY required")
    rows = fetch_new_feedback(since_hours=since_hours, limit=max_rows)
    log.info("fetched %d untriaged rows (last %dh)", len(rows), since_hours)
    results: list[dict] = []
    for row in rows:
        try:
            results.append(triage_one(row, dry_run=dry_run))
        except Exception as e:
            log.exception("triage failed for row %s: %s", row.get("id"), e)
            results.append({"id": row.get("id"), "error": str(e)})

    summary = {
        "total":       len(results),
        "bugs":        sum(1 for r in results if r.get("classification") == "bug"),
        "suggestions": sum(1 for r in results if r.get("classification") == "suggestion"),
        "content":     sum(1 for r in results if r.get("classification") == "content"),
        "noise":       sum(1 for r in results if r.get("classification") == "noise"),
        "duplicate":   sum(1 for r in results if r.get("classification") == "duplicate"),
        "errors":      sum(1 for r in results if r.get("error")),
        "issues_opened": sum(1 for r in results if r.get("issue_url")),
        "dry_run":     dry_run,
        "results":     results,
    }
    log.info("triage summary: %s", {k:v for k,v in summary.items() if k != "results"})
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--since-hours", type=int, default=48)
    p.add_argument("--max", type=int, default=50, dest="max_rows")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    out = run(since_hours=args.since_hours, max_rows=args.max_rows, dry_run=args.dry_run)
    print(json.dumps(out, indent=2, default=str))
