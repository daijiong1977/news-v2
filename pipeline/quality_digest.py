"""Daily quality digest — email a summary of the last N days of
published content to the project owner.

Reads payloads directly from Supabase Storage (no DB), so the
digest reflects what's actually live for users, not what the
pipeline THINKS it published. Per article (cat × story × level),
score word count + keyword coverage + image + source presence.
Per category per day, score source diversity.

Posts the HTML report to the existing `send-email-v2` edge
function (Gmail SMTP, already configured). No new infra.

Usage:
    python -m pipeline.quality_digest                 # send to QUALITY_DIGEST_TO
    python -m pipeline.quality_digest --dry-run       # print HTML, don't email
    python -m pipeline.quality_digest --days 7        # custom lookback
    python -m pipeline.quality_digest --to a@b.com    # override recipient
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib import error, parse, request
from zoneinfo import ZoneInfo

# All human-readable timestamps in the digest are rendered in ET so
# they match the project owner's wall clock — saves "is Apr 30
# correct? UTC says yes but I'm reading this on Apr 29 evening"
# confusion. Storage prefix dates (which the pipeline writes as
# wall-clock dates anyway) are left as-is.
ET = ZoneInfo("America/New_York")

log = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
# Recipient resolution: --to CLI flag overrides everything; otherwise
# fan out to every email in redesign_admin_users. Admins manage that
# table from the existing /admin.html UI — no separate config row.
DEFAULT_TO_FALLBACK = "self@daijiong.com"
DEFAULT_DAYS = int(os.environ.get("QUALITY_DIGEST_DAYS", "3"))


def _admin_emails() -> list[str]:
    """Pull every email from redesign_admin_users. Empty list on
    failure (caller falls back to hard-coded default)."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    url = f"{SUPABASE_URL}/rest/v1/redesign_admin_users?select=email&order=email"
    req = request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    })
    try:
        with request.urlopen(req, timeout=10) as r:
            rows = json.loads(r.read())
        emails = [str(r["email"]).strip() for r in rows if r.get("email")]
        return [e for e in emails if "@" in e]
    except Exception as e:
        log.warning("could not read admin emails: %s", e)
        return []


def resolve_recipients(cli_arg: str | None) -> list[str]:
    """Pick the list of recipients. CLI override → admin table → fallback."""
    if cli_arg:
        return [cli_arg.strip()]
    env_val = os.environ.get("QUALITY_DIGEST_TO")
    if env_val:
        return [e.strip() for e in env_val.split(",") if e.strip()]
    admins = _admin_emails()
    if admins:
        return admins
    log.warning("no admin emails found; falling back to %s", DEFAULT_TO_FALLBACK)
    return [DEFAULT_TO_FALLBACK]

STORAGE_BASE = f"{SUPABASE_URL}/storage/v1/object/public/redesign-daily-content"
SEND_EMAIL_URL = f"{SUPABASE_URL}/functions/v1/send-email-v2"

CATS  = ("news", "science", "fun")
# Only English levels are evaluated — cn is summary-only and lives
# in a different JSON shape that doesn't have body/keywords/why,
# so quality metrics aren't meaningful there.
LEVELS = ("easy", "middle")

# Body-length target per level — body is the FULL article text. In
# the per-story payload schema this lives in the field labeled
# `summary` (misleading; it's the body). Targets mirror the rewrite
# prompts in pipeline/news_rss_core.py.
BODY_TARGETS = {
    "easy":   (200, 320),
    "middle": (300, 410),
}
# Listing summary (short card blurb in articles_<cat>_<lvl>.json).
SUMMARY_MAX = 80
# Why-it-matters cap (per-story payload `why_it_matters`).
WHY_MAX = 80

# Slack on word-count gates: articles within ±15% of target still
# pass quality. The rewrite prompts target the core range, but
# DeepSeek routinely lands a few words over/under — penalising those
# would generate noisy "off"/"long" flags for content that's plenty
# good for kids. Trim/regenerate handlers in quality_autofix use the
# SAME slack so we don't churn on borderline cases.
WC_SLACK = 0.15


def _http_get(url: str, timeout: int = 30) -> tuple[int, bytes]:
    try:
        with request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read()
    except error.HTTPError as e:
        return e.code, e.read()


def _fetch_json(url: str) -> dict | None:
    code, body = _http_get(url)
    if code != 200:
        return None
    try:
        return json.loads(body)
    except Exception:
        return None


def _word_count(text: str) -> int:
    """English: whitespace-split words."""
    return len((text or "").split())


# ── Keyword matching (subset of news_rss_core, inlined to keep this
#    module dependency-light — the workflow installs requirements but
#    feedparser is unnecessary for digest). ─────────────────────────
_STEM_RULES = (
    ("ation", "at"), ("ies", "y"), ("acy", ""), ("atic", ""),
    ("ing", ""),     ("ed", ""),  ("es", ""), ("s", ""), ("e", ""),
)

def _stems(word: str) -> set[str]:
    s = {word}
    for suffix, replacement in _STEM_RULES:
        if word.endswith(suffix):
            s.add(word[: -len(suffix)] + replacement)
    return s


def _keyword_in_body(keyword: str, body: str) -> bool:
    if not keyword or not body:
        return False
    kw = keyword.strip().lower()
    body_lc = body.lower()
    # Tier 1: boundary-aware substring (handles multi-word phrases).
    if " " in kw:
        return kw in body_lc
    # Single word — guard against intra-word matches like Vegas/gas.
    if re.search(rf"(?<![A-Za-z]){re.escape(kw)}(?![A-Za-z])", body_lc):
        return True
    # Tier 2: stem intersection.
    body_words = re.findall(r"[A-Za-z]+", body_lc)
    kw_stems = _stems(kw)
    for w in body_words:
        if _stems(w) & kw_stems:
            return True
    return False


# ── Scoring ────────────────────────────────────────────────────────

def score_article(payload: dict, level: str, listing_summary: str = "") -> dict:
    """Compute per-article quality flags.

    Schema notes — easy to get wrong:
    - The per-story payload's `summary` field IS the article BODY
      (~340 words for middle, ~250 for easy). There is NO separate
      body field in the payload.
    - The actual short SUMMARY (the card blurb shown in listings) is
      passed in via `listing_summary` from the day's
      articles_<cat>_<lvl>.json.
    - `why_it_matters` is the small "why this matters" paragraph
      below the body in the reading view.
    """
    body = payload.get("summary") or ""           # NOT a typo: payload.summary IS body
    why  = payload.get("why_it_matters") or ""
    keywords_raw = payload.get("keywords") or []
    keyword_terms = [
        (k.get("term") if isinstance(k, dict) else str(k))
        for k in keywords_raw
    ]
    keyword_terms = [k for k in keyword_terms if k]

    body_wc = _word_count(body)
    summ_wc = _word_count(listing_summary)
    why_wc  = _word_count(why)

    lo, hi = BODY_TARGETS.get(level, (0, 9999))
    # ±15% slack on all word-count gates — see WC_SLACK definition.
    body_ok = (lo * (1 - WC_SLACK)) <= body_wc <= (hi * (1 + WC_SLACK))
    summ_ok = summ_wc <= SUMMARY_MAX * (1 + WC_SLACK)
    why_ok  = why_wc  <= WHY_MAX     * (1 + WC_SLACK)

    kw_hits = sum(1 for k in keyword_terms if _keyword_in_body(k, body))
    kw_total = len(keyword_terms)
    kw_ok = (kw_total == 0) or (kw_hits == kw_total)
    kw_misses = [k for k in keyword_terms if not _keyword_in_body(k, body)]

    image_ok  = bool(payload.get("image_url"))
    source_ok = bool(payload.get("source_name") or payload.get("source"))

    return {
        "body_wc":  body_wc,  "body_ok":  body_ok,
        "body_target": f"{lo}-{hi} (±15%)",
        "summary_wc": summ_wc, "summary_ok": summ_ok,
        "summary_target": f"≤{SUMMARY_MAX} (+15%)",
        "why_wc":   why_wc,    "why_ok":   why_ok,
        "why_target": f"≤{WHY_MAX} (+15%)",
        "kw_total": kw_total, "kw_hits": kw_hits, "kw_ok": kw_ok,
        "kw_misses": kw_misses[:5],
        "image_ok": image_ok, "source_ok": source_ok,
        "source": payload.get("source_name") or payload.get("source") or "",
        "title":  payload.get("title") or "",
        "all_ok": body_ok and summ_ok and why_ok and kw_ok and image_ok and source_ok,
    }


def gather_day(date_iso: str) -> dict:
    """Fetch listings + per-story payloads for one date. Returns
    a structured dict that the renderer walks."""
    out: dict = {"date": date_iso, "categories": {}, "missing_day": False}
    # Cheap listing-existence check via easy listing.
    probe = _fetch_json(f"{STORAGE_BASE}/{date_iso}/payloads/articles_news_easy.json")
    if probe is None:
        out["missing_day"] = True
        return out

    for cat in CATS:
        cat_block = {"stories": [], "sources": [], "diversity_ok": False}
        # Pull each level's listing once. The per-story payload doesn't
        # contain the short "card summary" the listing has — we need
        # to thread it in from here.
        listings: dict[str, dict] = {}
        for level in LEVELS:
            listings[level] = _fetch_json(
                f"{STORAGE_BASE}/{date_iso}/payloads/articles_{cat}_{level}.json"
            ) or {}
        # The easy listing is the canonical id source (top-3 picks
        # for the day for this category).
        story_ids = [a["id"] for a in (listings.get("easy") or {}).get("articles", [])[:3]]
        # Per-level lookup: story_id → listing entry.
        listing_by_lvl_sid: dict[str, dict[str, dict]] = {
            lvl: {a["id"]: a for a in (listings.get(lvl) or {}).get("articles", [])}
            for lvl in LEVELS
        }

        for sid in story_ids:
            story = {"id": sid, "levels": {}, "sources": set()}
            for level in LEVELS:
                url = f"{STORAGE_BASE}/{date_iso}/article_payloads/payload_{sid}/{level}.json"
                payload = _fetch_json(url)
                if not payload:
                    story["levels"][level] = {"missing": True}
                    continue
                listing_entry = listing_by_lvl_sid.get(level, {}).get(sid, {})
                listing_summary = listing_entry.get("summary", "")
                metrics = score_article(payload, level, listing_summary)
                story["levels"][level] = metrics
                if metrics["source"]:
                    story["sources"].add(metrics["source"])
            cat_block["stories"].append(story)
            cat_block["sources"].extend(story["sources"])
        # Diversity: top-3 stories should come from 3 distinct sources.
        # Use easy-level source as the canonical "source of the story".
        easy_sources = [
            s["levels"]["easy"]["source"]
            for s in cat_block["stories"]
            if s["levels"].get("easy") and not s["levels"]["easy"].get("missing")
        ]
        cat_block["diversity_ok"] = len(set(easy_sources)) == 3
        cat_block["distinct_source_count"] = len(set(easy_sources))
        out["categories"][cat] = cat_block
    return out


# ── Rendering ─────────────────────────────────────────────────────

def _badge(ok: bool, text: str) -> str:
    color = "#197a3b" if ok else "#a02b2b"
    bg    = "#ecfaf0" if ok else "#fff1f1"
    return (f'<span style="display:inline-block;padding:1px 6px;'
            f'border-radius:6px;font-size:11px;font-weight:700;'
            f'color:{color};background:{bg};">{text}</span>')


def _row_for_level(metrics: dict, level: str) -> str:
    if metrics.get("missing"):
        return (f'<tr><td>{level}</td>'
                f'<td colspan="6" style="color:#a02b2b">⚠ payload missing</td></tr>')
    cells = [
        f"<td>{level}</td>",
        f'<td>{metrics["body_wc"]} <span style="color:#888">/ {metrics["body_target"]}</span> '
            + _badge(metrics["body_ok"], "ok" if metrics["body_ok"] else "off") + "</td>",
        f'<td>{metrics["summary_wc"]} '
            + _badge(metrics["summary_ok"], "ok" if metrics["summary_ok"] else "long") + "</td>",
        f'<td>{metrics["why_wc"]} '
            + _badge(metrics["why_ok"], "ok" if metrics["why_ok"] else "long") + "</td>",
        (f'<td>{metrics["kw_hits"]}/{metrics["kw_total"]} '
            + _badge(metrics["kw_ok"], "ok" if metrics["kw_ok"] else f"miss: {', '.join(metrics['kw_misses'][:2])}") + "</td>"),
        f'<td>{_badge(metrics["image_ok"], "✓" if metrics["image_ok"] else "✗")}</td>',
        f'<td>{_badge(metrics["source_ok"], "✓" if metrics["source_ok"] else "✗")}</td>',
    ]
    return "<tr>" + "".join(cells) + "</tr>"


def fetch_pipeline_runs(days: int) -> list[dict]:
    """Pull recent redesign_runs entries with telemetry. Returns one
    row per run within the lookback window (which may be more than
    `days` rows if multiple runs per day). Falls back to [] on error."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    since = (datetime.now(ET).date() - timedelta(days=days)).isoformat()
    try:
        from urllib.parse import urlencode
        url = (f"{SUPABASE_URL}/rest/v1/redesign_runs?"
               + urlencode({
                   "select":   "run_date,status,started_at,finished_at,telemetry",
                   "run_date": f"gte.{since}",
                   "order":    "finished_at.desc",
                   "limit":    "30",
               }))
        req = request.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        })
        with request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        log.warning("could not read redesign_runs: %s", e)
        return []


def render_pipeline_runs_panel(runs: list[dict]) -> str:
    """For-tuning panel: per-run telemetry highlighting retries,
    truncations, fallbacks, warnings. Skip rows with nothing notable
    so the panel only fires when there's something to look at."""
    if not runs:
        return ''

    notable: list[str] = []
    for r in runs:
        tel = r.get("telemetry") or {}
        llm = tel.get("llm_calls") or {}
        warnings = tel.get("warnings") or []
        phases = tel.get("phases") or {}
        flags: list[str] = []

        ch_ret = llm.get("chat_retries", 0)
        ch_rep = llm.get("chat_repaired", 0)
        rs_cr  = llm.get("reasoner_content_retries", 0)
        rs_tr  = llm.get("reasoner_transport_retries", 0)
        rs_rep = llm.get("reasoner_repaired", 0)
        rs_trn = llm.get("reasoner_truncated", 0)

        if ch_ret:  flags.append(f'chat retries={ch_ret}')
        if ch_rep:  flags.append(f'chat JSON repaired={ch_rep}')
        if rs_cr:   flags.append(f'reasoner content retries={rs_cr}')
        if rs_tr:   flags.append(f'reasoner transport retries={rs_tr}')
        if rs_rep:  flags.append(f'reasoner JSON repaired={rs_rep}')
        if rs_trn:  flags.append(f'reasoner truncated={rs_trn}')

        # per-category exhausted sources
        for cat, cat_data in (tel.get("per_category") or {}).items():
            ex = cat_data.get("sources_exhausted") or []
            if ex:
                flags.append(f'{cat} exhausted: {", ".join(ex)}')

        if warnings:
            flags.append(f'{len(warnings)} warning(s): {"; ".join(warnings[:3])[:120]}')

        if not flags and r.get("status") == "completed":
            continue   # nothing to surface for this run

        # Wallclock seconds — sum of phases or computed from started/finished
        seconds = sum((phases.get(p) or {}).get("seconds", 0) for p in phases)
        mm = int(seconds // 60)

        line = f'<li><strong>{r["run_date"]}</strong>: {r["status"]} · {mm}m wallclock'
        if flags:
            line += ' · ' + ' · '.join(flags)
        line += '</li>'
        notable.append(line)

    if not notable:
        return ''   # everything clean — nothing to print

    return (
        '<div style="margin-top:14px;padding:14px 18px;background:#fafafa;'
        'border:1px solid #e5e5e5;border-radius:10px;font-size:12px;color:#444;">'
        '<div style="font-weight:700;font-size:13px;margin-bottom:8px;color:#1b1230;">'
        '🔧 Pipeline runs (notable telemetry only — for tuning)'
        '</div>'
        '<ul style="margin:0;padding-left:20px;line-height:1.55;">'
        + "".join(notable) +
        '</ul>'
        '</div>'
    )


# ── Escalated-rows panel ───────────────────────────────────────────
# When pipeline.autofix_apply can't fix a queued issue (LLM failure,
# unknown problem_type, etc.) it flips status to 'escalated'. The
# digest surfaces these with per-row buttons so the admin can decide:
# Dismiss / Resolve / 🤖 Fix-with-Claude (queues the local Mac listener).
# Each button URL is HMAC-signed against AUTOFIX_BUTTON_SECRET so an
# attacker can't mint links for rows they didn't see in the email.

import hashlib as _hashlib
import hmac as _hmac

AUTOFIX_BUTTON_SECRET = os.environ.get("AUTOFIX_BUTTON_SECRET", "")
ACTION_FN_URL = f"{SUPABASE_URL}/functions/v1/autofix-action"
# Cap visible rows to keep total link count manageable — Gmail
# silently drops emails with too many same-domain URLs.
ESCALATED_VISIBLE = 5


def _sign_action(row_id: int, action: str) -> str:
    msg = f"{row_id}|{action}".encode()
    return _hmac.new(
        AUTOFIX_BUTTON_SECRET.encode(), msg, _hashlib.sha256,
    ).hexdigest()[:16]


def _action_url(row_id: int, action: str) -> str:
    sig = _sign_action(row_id, action)
    return f"{ACTION_FN_URL}?id={row_id}&action={action}&sig={sig}"


def fetch_escalated_rows() -> list[dict]:
    try:
        from urllib.parse import urlencode
        url = (f"{SUPABASE_URL}/rest/v1/redesign_autofix_queue?"
               + urlencode({
                   "select":   "id,published_date,story_id,level,problem_type,"
                               "attempts,agent_log,last_attempt_at",
                   "status":   "eq.escalated",
                   "order":    "last_attempt_at.desc.nullslast",
                   "limit":    "20",
               }))
        req = request.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        })
        with request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        log.warning("escalated rows fetch failed: %s", e)
        return []


def render_escalated_panel(rows: list[dict]) -> str:
    if not rows:
        return ""
    if not AUTOFIX_BUTTON_SECRET:
        log.warning("AUTOFIX_BUTTON_SECRET not set — skipping escalated panel")
        return ""

    visible = rows[:ESCALATED_VISIBLE]
    overflow = max(0, len(rows) - ESCALATED_VISIBLE)
    n = len(rows)

    item_blocks: list[str] = []
    for r in visible:
        rid = r["id"]
        msg = ""
        try:
            log_obj = json.loads(r.get("agent_log") or "{}")
            msg = log_obj.get("escalated_msg") or log_obj.get("resolved_msg") or ""
        except Exception:
            msg = (r.get("agent_log") or "")[:140]
        url_dismiss = _action_url(rid, "dismiss")
        url_resolve = _action_url(rid, "resolve")
        url_fix     = _action_url(rid, "fix")
        item_blocks.append(
            '<div style="border:1px solid #f0e5d0;border-radius:8px;'
            'padding:12px 14px;margin-bottom:10px;background:#fffaf0;">'
            f'<div style="font-size:13px;color:#1b1230;font-weight:600;">'
            f'{r["story_id"]} · {r["level"]} · '
            f'<code style="font-size:12px;color:#a25c10;">{r["problem_type"]}</code>'
            f'</div>'
            f'<div style="font-size:12px;color:#555;margin:4px 0 10px;">{msg}</div>'
            f'<a href="{url_fix}" '
            'style="display:inline-block;padding:7px 14px;margin-right:6px;'
            'background:#1b1230;color:#fff;text-decoration:none;'
            'border-radius:6px;font-weight:700;font-size:12px;">🤖 Fix with Claude</a>'
            f'<a href="{url_resolve}" '
            'style="display:inline-block;padding:7px 14px;margin-right:6px;'
            'background:#fff;color:#197a3b;border:1px solid #b6e3c5;'
            'text-decoration:none;border-radius:6px;font-weight:700;font-size:12px;">Resolve</a>'
            f'<a href="{url_dismiss}" '
            'style="display:inline-block;padding:7px 14px;'
            'background:#fff;color:#666;border:1px solid #ddd;'
            'text-decoration:none;border-radius:6px;font-weight:700;font-size:12px;">Dismiss</a>'
            '</div>'
        )
    overflow_note = (
        f'<div style="font-size:12px;color:#7a4d18;margin-top:6px;">'
        f'… and {overflow} more escalated. Re-queued at next pipeline run if still failing.</div>'
        if overflow else ''
    )
    return (
        '<div style="margin-bottom:18px;padding:18px 20px;'
        'background:#fff5e8;border:1px solid #ffd9a0;border-radius:10px;'
        'color:#7a4d18;">'
        f'<div style="font-weight:700;font-size:15px;margin-bottom:10px;">'
        f'⚠ {n} item{"s" if n != 1 else ""} escalated — your call'
        f'</div>'
        '<div style="font-size:12px;color:#7a4d18;margin-bottom:12px;">'
        'Routine auto-fix gave up on these. Pick an action per row:'
        '</div>'
        + ''.join(item_blocks) + overflow_note +
        '</div>'
    )


# ── PR review panel + rollback panel ──────────────────────────────
# Surfaces claude-opened PRs that need human approval, plus recently
# merged PRs the admin can roll back if they don't like the result.

PR_VISIBLE = 3                # cap per section to stay under Gmail's
                              # multi-link drop heuristic
ROLLBACK_WINDOW_DAYS = 7      # how long after merge to keep offering rollback


def _pr_action_url(pr_num: int, action: str) -> str:
    if not AUTOFIX_BUTTON_SECRET:
        return ""
    sig = _hmac.new(
        AUTOFIX_BUTTON_SECRET.encode(),
        f"pr|{pr_num}|{action}".encode(),
        _hashlib.sha256,
    ).hexdigest()[:16]
    return f"{ACTION_FN_URL}?pr={pr_num}&action={action}&sig={sig}"


def fetch_open_prs() -> list[dict]:
    """Queue rows that opened a PR which is still OPEN waiting for
    admin Merge/Close. pr_state='open' is set by the consumer when
    claude opens a PR; the edge fn flips it to 'merged' or 'closed'
    when the admin clicks a button."""
    try:
        from urllib.parse import urlencode
        url = (f"{SUPABASE_URL}/rest/v1/redesign_autofix_queue?"
               + urlencode({
                   "select": "id,pr_number,github_issue_number,problem_type,agent_log,resolved_at",
                   "pr_state": "eq.open",
                   "order": "resolved_at.desc.nullslast",
                   "limit": "20",
               }))
        req = request.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        })
        with request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        log.warning("open PRs fetch failed: %s", e)
        return []


def fetch_rollbackable_prs() -> list[dict]:
    """Recently merged PRs (within ROLLBACK_WINDOW_DAYS) that haven't
    been confirmed-kept yet. These get [Rollback] [Looks good] buttons
    so the admin can undo a regrettable change after seeing it live."""
    try:
        from urllib.parse import urlencode
        cutoff = (datetime.now(timezone.utc) - timedelta(days=ROLLBACK_WINDOW_DAYS)).isoformat()
        url = (f"{SUPABASE_URL}/rest/v1/redesign_autofix_queue?"
               + urlencode({
                   "select": "id,pr_number,github_issue_number,agent_log,pr_merged_at,problem_detail",
                   "pr_state": "eq.merged",
                   "pr_merged_at": f"gte.{cutoff}",
                   "order": "pr_merged_at.desc",
                   "limit": "10",
               }))
        req = request.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        })
        with request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        log.warning("rollbackable PRs fetch failed: %s", e)
        return []


def _pr_summary_line(row: dict) -> str:
    """Shorten claude's RESOLVED log into a one-liner for the email."""
    log_str = row.get("agent_log") or ""
    for line in log_str.splitlines():
        line = line.strip()
        if line.startswith("RESOLVED:"):
            return line[len("RESOLVED:"):].strip()[:200]
    issue = row.get("github_issue_number")
    return (f"PR resolves issue #{issue}" if issue else "PR opened by autofix")[:200]


def render_pr_review_panel(rows: list[dict]) -> str:
    if not rows or not AUTOFIX_BUTTON_SECRET:
        return ""
    visible = rows[:PR_VISIBLE]
    overflow = max(0, len(rows) - PR_VISIBLE)

    blocks: list[str] = []
    for r in visible:
        prn = r["pr_number"]
        issue = r.get("github_issue_number")
        title = _pr_summary_line(r)
        u_merge = _pr_action_url(prn, "merge")
        u_close = _pr_action_url(prn, "close")
        u_leave = _pr_action_url(prn, "leave")
        gh_url  = f"https://github.com/daijiong1977/news-v2/pull/{prn}"
        issue_chip = (
            f' · <a href="https://github.com/daijiong1977/news-v2/issues/{issue}" '
            f'style="color:#888;">closes #{issue}</a>'
        ) if issue else ''
        blocks.append(
            '<div style="border:1px solid #d6e6f3;border-radius:8px;'
            'padding:12px 14px;margin-bottom:10px;background:#f0f7fb;">'
            f'<div style="font-size:13px;color:#1b1230;font-weight:600;">'
            f'<a href="{gh_url}" style="color:#1b1230;">PR #{prn}</a>{issue_chip}'
            f'</div>'
            f'<div style="font-size:12px;color:#555;margin:4px 0 10px;">{title}</div>'
            f'<a href="{u_merge}" '
            'style="display:inline-block;padding:7px 14px;margin-right:6px;'
            'background:#197a3b;color:#fff;text-decoration:none;'
            'border-radius:6px;font-weight:700;font-size:12px;">Merge</a>'
            f'<a href="{u_close}" '
            'style="display:inline-block;padding:7px 14px;margin-right:6px;'
            'background:#fff;color:#a02b2b;border:1px solid #f5c6c6;'
            'text-decoration:none;border-radius:6px;font-weight:700;font-size:12px;">Close</a>'
            f'<a href="{u_leave}" '
            'style="display:inline-block;padding:7px 14px;'
            'background:#fff;color:#666;border:1px solid #ddd;'
            'text-decoration:none;border-radius:6px;font-weight:700;font-size:12px;">Leave for review</a>'
            '</div>'
        )
    overflow_note = (
        f'<div style="font-size:12px;color:#1b5285;margin-top:6px;">'
        f'… and {overflow} more PRs open. Tomorrow\'s digest will surface them again.</div>'
        if overflow else ''
    )
    n = len(rows)
    return (
        '<div style="margin-bottom:18px;padding:18px 20px;'
        'background:#f0f7fb;border:1px solid #c0d8eb;border-radius:10px;color:#1b5285;">'
        f'<div style="font-weight:700;font-size:15px;margin-bottom:10px;">'
        f'🔧 {n} PR{"s" if n != 1 else ""} ready for review</div>'
        '<div style="font-size:12px;color:#1b5285;margin-bottom:12px;">'
        'claude opened these. <strong>Merge</strong> squashes into main + Vercel redeploys; '
        '<strong>Close</strong> drops the change; <strong>Leave</strong> shows again tomorrow.'
        '</div>'
        + ''.join(blocks) + overflow_note + '</div>'
    )


def render_rollback_panel(rows: list[dict]) -> str:
    if not rows or not AUTOFIX_BUTTON_SECRET:
        return ""
    visible = rows[:PR_VISIBLE]
    overflow = max(0, len(rows) - PR_VISIBLE)

    blocks: list[str] = []
    for r in visible:
        prn = r["pr_number"]
        issue = r.get("github_issue_number")
        title = _pr_summary_line(r)
        merged_at = (r.get("pr_merged_at") or "")[:10]   # YYYY-MM-DD
        u_rollback = _pr_action_url(prn, "rollback")
        u_keep     = _pr_action_url(prn, "keep")
        gh_url  = f"https://github.com/daijiong1977/news-v2/pull/{prn}"
        issue_chip = (
            f' · #{issue}' if issue else ''
        )
        blocks.append(
            '<div style="border:1px solid #e6e6e6;border-radius:8px;'
            'padding:12px 14px;margin-bottom:10px;background:#fafafa;">'
            f'<div style="font-size:13px;color:#1b1230;font-weight:600;">'
            f'<a href="{gh_url}" style="color:#1b1230;">PR #{prn}</a>{issue_chip} '
            f'<span style="font-weight:400;color:#888;font-size:12px;">merged {merged_at}</span>'
            f'</div>'
            f'<div style="font-size:12px;color:#555;margin:4px 0 10px;">{title}</div>'
            f'<a href="{u_rollback}" '
            'style="display:inline-block;padding:7px 14px;margin-right:6px;'
            'background:#fff;color:#a02b2b;border:1px solid #f5c6c6;'
            'text-decoration:none;border-radius:6px;font-weight:700;font-size:12px;">Rollback</a>'
            f'<a href="{u_keep}" '
            'style="display:inline-block;padding:7px 14px;'
            'background:#fff;color:#197a3b;border:1px solid #b6e3c5;'
            'text-decoration:none;border-radius:6px;font-weight:700;font-size:12px;">Looks good</a>'
            '</div>'
        )
    overflow_note = (
        f'<div style="font-size:12px;color:#666;margin-top:6px;">'
        f'… and {overflow} more in the {ROLLBACK_WINDOW_DAYS}-day rollback window.</div>'
        if overflow else ''
    )
    n = len(rows)
    return (
        '<div style="margin-bottom:18px;padding:18px 20px;'
        'background:#fafafa;border:1px solid #e6e6e6;border-radius:10px;color:#444;">'
        f'<div style="font-weight:700;font-size:15px;margin-bottom:10px;">'
        f'↺ {n} merge{"s" if n != 1 else ""} from the last {ROLLBACK_WINDOW_DAYS} days</div>'
        '<div style="font-size:12px;color:#666;margin-bottom:12px;">'
        '<strong>Rollback</strong> reverts the merge on main (Vercel redeploys); '
        '<strong>Looks good</strong> dismisses from this list.'
        '</div>'
        + ''.join(blocks) + overflow_note + '</div>'
    )


# ── Queue summary panel (still queued, never tried) ────────────────


def fetch_queue_summary() -> dict:
    """Pull current redesign_autofix_queue state for the pending-fixes
    panel. Returns {count, items} where items is a list of brief
    descriptors. Falls back to empty on any error — the digest must
    still render even if Supabase is flaky."""
    try:
        from urllib.parse import urlencode
        url = (f"{SUPABASE_URL}/rest/v1/redesign_autofix_queue?"
               + urlencode({
                   "select":   "id,published_date,story_id,level,problem_type,attempts,created_at",
                   "status":   "eq.queued",
                   "order":    "created_at.asc",
                   "limit":    "50",
               }))
        req = request.Request(url, headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
        })
        with request.urlopen(req, timeout=15) as r:
            rows = json.loads(r.read())
        return {"count": len(rows), "items": rows}
    except Exception as e:
        log.warning("queue fetch failed: %s", e)
        return {"count": 0, "items": []}


def render_pending_fixes_panel(queue: dict) -> str:
    """Single-CTA panel that links to the autofix-review browser
    control panel. This deliberately keeps the email body to ONE
    https link — multi-link emails to supabase.co URLs were getting
    silently dropped by Gmail's bulk-mail filter (not even spam'd,
    just gone). The control panel itself has all the per-item action
    buttons; the email is just the doorbell."""
    n = queue.get("count", 0)
    # Static HTML page on news.6ray.com (cleanUrls-stripped path).
    # Originally tried Supabase Edge Functions for this, but Supabase
    # forces all edge-function HTML responses to text/plain + sandbox
    # CSP + nosniff (anti-phishing default), which made the page
    # render as plain HTML markup text in browsers. The Vercel-hosted
    # static page bypasses that.
    review_url = "https://news.6ray.com/autofix"

    if n == 0:
        return ('<div style="margin-bottom:18px;padding:12px 16px;'
                'background:#ecfaf0;border-radius:8px;font-size:13px;color:#197a3b;">'
                '✓ Autofix queue empty — nothing pending. (Daily report still sent so you '
                'know the pipeline ran.)'
                '</div>')

    # Brief item summary (text only — no per-item links). The full
    # control panel is one click away.
    item_lines: list[str] = []
    for item in queue["items"][:5]:
        sid = item.get("story_id", "")
        level = item.get("level", "")
        ptype = item.get("problem_type", "")
        item_lines.append(f'<li><code style="font-size:11px;">{sid}</code> · {level} · {ptype}</li>')
    if n > 5:
        item_lines.append(f'<li style="color:#888;">… and {n - 5} more</li>')

    return (
        '<div style="margin-bottom:18px;padding:18px 20px;'
        'background:#fff5e8;border:1px solid #ffd9a0;border-radius:10px;'
        'color:#7a4d18;">'
        f'<div style="font-weight:700;font-size:15px;margin-bottom:8px;">'
        f'⚠ {n} pending autofix item{"s" if n != 1 else ""}'
        f'</div>'
        '<ul style="margin:0 0 14px;padding-left:20px;font-size:13px;line-height:1.6;color:#1b1230;">'
        + "".join(item_lines) +
        '</ul>'
        f'<a href="{review_url}" '
        'style="display:inline-block;padding:11px 22px;'
        'background:#1b1230;color:#fff;text-decoration:none;'
        'border-radius:8px;font-weight:700;font-size:14px;">'
        '🛠️ Review pending fixes →</a>'
        '<div style="margin-top:10px;font-size:11px;color:#7a4d18;">'
        'Opens a control panel in your browser with Fix / Dismiss / Resolved '
        'buttons per item. Bookmark the URL — it\'s always live.'
        '</div>'
        '</div>'
    )


def _count_pass_fail(days: list[dict]) -> tuple[int, int]:
    """Return (total_variants, bad_variants) across all days."""
    total = 0
    bad = 0
    for d in days:
        if d.get("missing_day"):
            continue
        for cat in d.get("categories", {}).values():
            for s in cat["stories"]:
                for lvl_metrics in s["levels"].values():
                    total += 1
                    if lvl_metrics.get("missing"):
                        bad += 1
                    elif not lvl_metrics.get("all_ok"):
                        bad += 1
    return total, bad


def render_html(days: list[dict], queue: dict | None = None) -> str:
    lines: list[str] = []
    lines.append("<!doctype html><html><body style=\"font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#222;background:#f7f5f0;padding:18px;\">")
    lines.append('<div style="max-width:880px;margin:0 auto;background:#fff;border-radius:10px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.05);">')
    lines.append('<h1 style="margin:0 0 4px;font-size:22px;color:#1b1230;">📊 Kids News — Quality Digest</h1>')
    now_et = datetime.now(ET)
    lines.append(f'<div style="font-size:12px;color:#888;margin-bottom:18px;">Generated {now_et.strftime("%Y-%m-%d %H:%M %Z")} · last {len(days)} days</div>')

    # PRs ready for review — at the very top because deciding on them
    # is the most time-sensitive thing the admin can do today.
    open_prs = fetch_open_prs()
    if open_prs:
        lines.append(render_pr_review_panel(open_prs))

    # Escalated rows — auto-fix gave up, admin must pick an action.
    escalated_rows = fetch_escalated_rows()
    if escalated_rows:
        lines.append(render_escalated_panel(escalated_rows))

    # Pending-fixes panel — items still queued (auto-fix hasn't run yet
    # for some reason, or admin's earlier dismissed items got re-queued
    # by tomorrow's scan).
    if queue is not None:
        lines.append(render_pending_fixes_panel(queue))

    # Recently merged — rollback window. Lower priority because these
    # are post-decision; surface AFTER the items needing decisions.
    rollback_rows = fetch_rollbackable_prs()
    if rollback_rows:
        lines.append(render_rollback_panel(rollback_rows))

    total_variants, bad_variants = _count_pass_fail(days)
    queue_count = (queue or {}).get("count", 0)
    escalated_count = len(escalated_rows)
    open_pr_count = len(open_prs)
    rollback_count = len(rollback_rows)

    # Pull recent pipeline runs for the tuning panel.
    pipeline_runs = fetch_pipeline_runs(len(days))
    pipeline_panel = render_pipeline_runs_panel(pipeline_runs)

    # Clean-day shortcut: if every article passed AND nothing pending,
    # don't bother with the per-day tables. Just confirm "today is good"
    # without listing every checked date — user only wants to see dates
    # that have something wrong.
    if (bad_variants == 0 and queue_count == 0 and escalated_count == 0
            and open_pr_count == 0 and rollback_count == 0):
        today_label = days[0]["date"] if days else datetime.now(ET).date().isoformat()
        missing = [d["date"] for d in days if d.get("missing_day")]
        lines.append(
            '<div style="margin-top:20px;padding:36px 20px;background:#ecfaf0;'
            'border-radius:10px;text-align:center;color:#197a3b;">'
            '<div style="font-size:54px;margin-bottom:10px;">🎉</div>'
            '<div style="font-size:22px;font-weight:700;margin-bottom:6px;">'
            f'{today_label} — everything is good!'
            '</div>'
            f'<div style="font-size:14px;color:#222;">'
            f'All {total_variants} article variants passed all checks. No items pending.'
            '</div>'
            '</div>'
        )
        if missing:
            lines.append(
                '<div style="margin-top:14px;padding:10px 14px;background:#fff5e8;'
                'border-radius:8px;font-size:12px;color:#7a4d18;">'
                f'⚠ No listings published on: {", ".join(missing)}. '
                'Possibly the pipeline cron didn\'t fire — check daily-pipeline workflow.'
                '</div>'
            )
        if pipeline_panel:
            lines.append(pipeline_panel)
        lines.append('<div style="font-size:11px;color:#aaa;margin-top:16px;">'
                      'Source: <code>redesign-daily-content</code> storage. '
                      'Detailed report skipped because nothing needs your attention. '
                      'Generated by <code>pipeline.quality_digest</code>.</div>')
        lines.append("</div></body></html>")
        return "".join(lines)

    # There's at least one issue. List failing articles tersely with
    # the specific failed metric — NO full per-day tables. The
    # pending-fixes panel above already gives the action buttons; this
    # block just clarifies anything detected at storage scan time
    # that didn't make it into the queue (mostly edge cases).
    issue_lines: list[str] = []
    for d in days:
        if d.get("missing_day"):
            issue_lines.append(
                f'<li><strong>{d["date"]}</strong>: '
                'no listings published — pipeline cron may not have fired. '
                '<em>Fix:</em> check daily-pipeline workflow runs in GitHub Actions.</li>'
            )
            continue
        for cat, block in d.get("categories", {}).items():
            if not block["diversity_ok"]:
                issue_lines.append(
                    f'<li><strong>{d["date"]} · {cat.upper()}</strong>: '
                    f'only {block["distinct_source_count"]}/3 distinct sources. '
                    '<em>Fix:</em> add more sources to this category in admin → Sources, or rerun pipeline.</li>'
                )
            for story in block["stories"]:
                for level in LEVELS:
                    m = story["levels"].get(level) or {"missing": True}
                    if m.get("missing"):
                        issue_lines.append(
                            f'<li><strong>{story["id"]} · {level}</strong>: '
                            'payload file missing. '
                            '<em>Fix:</em> rerun pipeline rewrite + persist for this story.</li>'
                        )
                        continue
                    if m.get("all_ok"):
                        continue
                    # Compose the specific issues for this article.
                    issues: list[str] = []
                    fixes: list[str] = []
                    if not m.get("body_ok"):
                        issues.append(f'body {m["body_wc"]} words (target {m["body_target"]})')
                        fixes.append('🛠️ Fix on the panel will re-rewrite body to fit')
                    if not m.get("summary_ok"):
                        issues.append(f'summary {m["summary_wc"]} words (target {m["summary_target"]})')
                        fixes.append('listing-summary trim runs automatically next pipeline')
                    if not m.get("why_ok"):
                        issues.append(f'why_it_matters {m["why_wc"]} words (target {m["why_target"]})')
                        fixes.append('🛠️ Fix → trim + re-prompt')
                    if not m.get("kw_ok"):
                        miss = m.get("kw_misses") or []
                        miss_str = ", ".join(f'"{k}"' for k in miss[:3])
                        issues.append(f'keyword miss: {miss_str}')
                        fixes.append('🛠️ Fix → agent decides to weave in or remove bogus keyword')
                    if not m.get("image_ok"):
                        issues.append('image missing')
                        fixes.append('🛠️ Fix → re-trigger image generator')
                    if not m.get("source_ok"):
                        issues.append('source attribution missing')
                        fixes.append('manual: edit listing JSON in admin')
                    issue_text = "; ".join(issues)
                    fix_text = " · ".join(set(fixes))   # de-dup
                    issue_lines.append(
                        f'<li><strong>{story["id"]} · {level}</strong>: '
                        f'{issue_text}. '
                        f'<em>Fix:</em> {fix_text}.</li>'
                    )

    if issue_lines:
        lines.append(
            '<div style="margin-top:14px;padding:14px 18px;background:#fff1f1;'
            'border:1px solid #f5c6c6;border-radius:10px;color:#1b1230;">'
            '<div style="font-weight:700;font-size:14px;color:#a02b2b;margin-bottom:8px;">'
            f'⚠ {len(issue_lines)} quality issue{"s" if len(issue_lines) != 1 else ""} detected'
            '</div>'
            '<ul style="margin:0;padding-left:20px;font-size:13px;line-height:1.55;">'
            + "".join(issue_lines) +
            '</ul>'
            '</div>'
        )

    lines.append(f'<div style="margin-top:18px;padding:10px 14px;background:#fafafa;border-radius:8px;font-size:12px;color:#666;">'
                  f'{total_variants - bad_variants} / {total_variants} article variants passed all checks.</div>')
    if pipeline_panel:
        lines.append(pipeline_panel)
    lines.append('<div style="font-size:11px;color:#aaa;margin-top:14px;">Source: <code>redesign-daily-content</code> storage. '
                  'Generated by <code>pipeline.quality_digest</code>.</div>')
    lines.append("</div></body></html>")
    return "".join(lines)


def send_email(to: str, subject: str, html: str) -> bool:
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("missing SUPABASE_URL/SUPABASE_SERVICE_KEY")
        return False
    body = json.dumps({
        "to_email": to,
        "subject":  subject,
        "html":     html,
        "from_name": "Kids News Pipeline",
    }).encode()
    req = request.Request(
        SEND_EMAIL_URL, method="POST", data=body,
        headers={
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=30) as r:
            resp = r.read().decode()
        log.info("email send: %s", resp[:200])
        return True
    except error.HTTPError as e:
        log.error("email send failed: %s %s", e.code, e.read().decode()[:200])
        return False


def run(days: int, recipients: list[str], dry_run: bool) -> dict:
    # "Today" anchors on the user's wall clock (ET) — without this,
    # an evening run at 23:30 ET on Apr 29 (= 03:30 UTC Apr 30)
    # would label its digest "Apr 30" and confuse the reader.
    today = datetime.now(ET).date()
    targets = [(today - timedelta(days=i)).isoformat() for i in range(days)]
    log.info("gathering %d days (ET-anchored): %s", days, targets)
    day_blocks = [gather_day(d) for d in targets]
    queue = fetch_queue_summary()
    log.info("autofix queue: %d items pending", queue.get("count", 0))
    html = render_html(day_blocks, queue=queue)
    # Subject is ASCII-only by design. RFC 2047 encoded-words (used to
    # carry emoji / em-dash / middle-dot) get displayed as raw
    # =?utf-8?Q?...?= text in some email clients that don't decode
    # multi-chunk encoded-words correctly. ASCII subjects bypass that
    # entirely, render anywhere, and Gmail spam filters like them
    # better too.
    pend_suffix = f" - {queue['count']} pending fix{'es' if queue['count'] != 1 else ''}" if queue["count"] else ""
    subject = f"Kids News quality - {today.isoformat()} ET (last {days}d){pend_suffix}"
    if dry_run:
        sys.stdout.write(html)
        return {"dry_run": True, "subject": subject, "bytes": len(html), "recipients": recipients}

    # Send one email per recipient. send-email-v2's `to` field accepts
    # a single address; iterating keeps each delivery independently
    # logged/retried at the SMTP layer rather than risking one bad
    # address torpedoing the rest.
    results = []
    for to in recipients:
        ok = send_email(to, subject, html)
        results.append({"to": to, "sent": ok})
        if not ok:
            log.warning("send failed for %s", to)
    any_sent = any(r["sent"] for r in results)
    return {
        "dry_run": False, "subject": subject,
        "recipients": recipients, "results": results, "sent": any_sent,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                         format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days", type=int, default=DEFAULT_DAYS)
    p.add_argument("--to", default=None,
                   help="Override recipient. Default = every email in "
                        "redesign_admin_users (or env QUALITY_DIGEST_TO, "
                        "or " + DEFAULT_TO_FALLBACK + " as last resort).")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    recipients = resolve_recipients(args.to)
    log.info("recipients resolved to: %s", recipients)
    out = run(days=args.days, recipients=recipients, dry_run=args.dry_run)
    if not args.dry_run:
        print(json.dumps(out, indent=2))
        sys.exit(0 if out.get("sent") else 1)
