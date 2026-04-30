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
DEFAULT_TO   = os.environ.get("QUALITY_DIGEST_TO", "self@daijiong.com")
DEFAULT_DAYS = int(os.environ.get("QUALITY_DIGEST_DAYS", "3"))

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
    body_ok = lo <= body_wc <= hi
    summ_ok = summ_wc <= SUMMARY_MAX
    why_ok  = why_wc  <= WHY_MAX

    kw_hits = sum(1 for k in keyword_terms if _keyword_in_body(k, body))
    kw_total = len(keyword_terms)
    kw_ok = (kw_total == 0) or (kw_hits == kw_total)
    kw_misses = [k for k in keyword_terms if not _keyword_in_body(k, body)]

    image_ok  = bool(payload.get("image_url"))
    source_ok = bool(payload.get("source_name") or payload.get("source"))

    return {
        "body_wc":  body_wc,  "body_ok":  body_ok,
        "body_target": f"{lo}-{hi}",
        "summary_wc": summ_wc, "summary_ok": summ_ok,
        "summary_target": f"≤{SUMMARY_MAX}",
        "why_wc":   why_wc,    "why_ok":   why_ok,
        "why_target": f"≤{WHY_MAX}",
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


def render_html(days: list[dict], queue: dict | None = None) -> str:
    lines: list[str] = []
    lines.append("<!doctype html><html><body style=\"font-family:-apple-system,Segoe UI,Roboto,sans-serif;color:#222;background:#f7f5f0;padding:18px;\">")
    lines.append('<div style="max-width:880px;margin:0 auto;background:#fff;border-radius:10px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.05);">')
    lines.append('<h1 style="margin:0 0 4px;font-size:22px;color:#1b1230;">📊 Kids News — Quality Digest</h1>')
    now_et = datetime.now(ET)
    lines.append(f'<div style="font-size:12px;color:#888;margin-bottom:18px;">Generated {now_et.strftime("%Y-%m-%d %H:%M %Z")} · last {len(days)} days</div>')

    # Pending-fixes panel — at the top so the user sees it first.
    if queue is not None:
        lines.append(render_pending_fixes_panel(queue))

    for day in days:
        date = day["date"]
        lines.append(f'<h2 style="font-size:18px;color:#1b1230;border-bottom:2px solid #ffc83d;padding-bottom:6px;margin-top:22px;">{date}</h2>')
        if day.get("missing_day"):
            lines.append('<div style="color:#a02b2b;font-size:14px;">⚠ no listings published this day (storage prefix empty)</div>')
            continue
        for cat, block in day["categories"].items():
            div_text = f'{block["distinct_source_count"]}/3 distinct sources'
            div_badge = _badge(block["diversity_ok"], div_text)
            lines.append(f'<h3 style="font-size:15px;margin-top:14px;color:#1b1230;">{cat.upper()} &nbsp; {div_badge}</h3>')
            for story in block["stories"]:
                first_title = ""
                for level in LEVELS:
                    m = story["levels"].get(level) or {}
                    if not m.get("missing") and m.get("title"):
                        first_title = m["title"]
                        break
                lines.append(f'<div style="font-weight:700;font-size:13px;margin:10px 0 4px;">{story["id"]} — {first_title[:90]}</div>')
                lines.append('<table style="width:100%;border-collapse:collapse;font-size:12px;">')
                lines.append(
                    "<thead><tr style='background:#fafafa;color:#666;text-align:left;'>"
                    "<th style='padding:4px 6px;width:60px;'>level</th>"
                    "<th style='padding:4px 6px;'>body</th>"
                    "<th style='padding:4px 6px;'>summary</th>"
                    "<th style='padding:4px 6px;'>why</th>"
                    "<th style='padding:4px 6px;'>keywords</th>"
                    "<th style='padding:4px 6px;'>img</th>"
                    "<th style='padding:4px 6px;'>src</th>"
                    "</tr></thead><tbody>"
                )
                for level in LEVELS:
                    m = story["levels"].get(level)
                    if m is None:
                        m = {"missing": True}
                    lines.append(_row_for_level(m, level))
                lines.append("</tbody></table>")
    # Summary footer
    total_articles = 0
    bad_articles = 0
    for d in days:
        for cat in d.get("categories", {}).values():
            for s in cat["stories"]:
                for lvl_metrics in s["levels"].values():
                    if lvl_metrics.get("missing"):
                        bad_articles += 1
                        total_articles += 1
                        continue
                    total_articles += 1
                    if not lvl_metrics.get("all_ok"):
                        bad_articles += 1
    lines.append(f'<div style="margin-top:24px;padding:12px;background:#fafafa;border-radius:8px;font-size:13px;">'
                  f'<strong>Overall:</strong> {total_articles - bad_articles} / {total_articles} article variants passed all checks. '
                  f'{ "🎉" if bad_articles == 0 else "🔍 review reds above" }</div>')
    lines.append('<div style="font-size:11px;color:#aaa;margin-top:16px;">Source: <code>redesign-daily-content</code> storage. '
                  'Generated by <code>pipeline.quality_digest</code> · feedback#10 / issue#5.</div>')
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


def run(days: int, to: str, dry_run: bool) -> dict:
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
    pend_suffix = f" · {queue['count']} pending fix{'es' if queue['count'] != 1 else ''}" if queue["count"] else ""
    subject = f"📊 Kids News quality — {today.isoformat()} ET (last {days}d){pend_suffix}"
    if dry_run:
        sys.stdout.write(html)
        return {"dry_run": True, "subject": subject, "bytes": len(html)}
    ok = send_email(to, subject, html)
    return {"dry_run": False, "to": to, "subject": subject, "sent": ok}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                         format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days", type=int, default=DEFAULT_DAYS)
    p.add_argument("--to", default=DEFAULT_TO)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    out = run(days=args.days, to=args.to, dry_run=args.dry_run)
    if not args.dry_run:
        print(json.dumps(out, indent=2))
        sys.exit(0 if out.get("sent") else 1)
