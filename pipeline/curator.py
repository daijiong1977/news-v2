"""Step 2 (News-lane only) — CURATOR: single DeepSeek call over all candidates.

Returns {duplicates, picks, alternates} with hard rules enforced in Python.
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests

from . import config as cfg

log = logging.getLogger(__name__)


CURATOR_SYSTEM_PROMPT = """You are curating kid-appropriate news for ages 8-13.

You have 15 news story briefs, grouped by source:
- GROUP A (Tier 1): NPR, Reuters
- GROUP B (Tier 2): AP, BBC, Guardian
- GROUP C (RSS): PBS NewsHour

TASK 1 — Detect cross-group duplicates.
When the same event is covered by 2+ groups, that's a "hot news" signal.
List clusters of brief-IDs that cover the same story and a one-line reason.

TASK 2 — Pick exactly 3 stories for publishing.
HARD RULES (must follow):
  R1: Exactly 3 picks.
  R2: If any Group C (RSS) brief is given and reasonable, 1 of the 3 MUST be Group C.
  R3: The OTHER 2 picks must come from DIFFERENT outlets (not 2 from same host —
      e.g., not both from npr.org, not both from bbc.com).
  R4: Prefer cross-group hot duplicates.
  R5: Avoid: gossip, obituaries, pure politics without story angle,
      sponsored/affiliate content, jargon-heavy business news without kid relevance.
  R6: Prefer: important world events, mini-stories with human or kid interest,
      surprising discoveries, narrative quality.

TASK 3 — Also list 2-3 alternate picks (ranked) in case a pick fails later safety/interest vet.

Return ONLY valid JSON (no markdown fences):
{
  "duplicates": [
    {"ids": ["id1", "id2"], "reason": "..."}
  ],
  "picks": [
    {"id": "...", "reason": "...", "is_hot_duplicate": true, "source_group": "A"},
    {"id": "...", "reason": "...", "is_hot_duplicate": false, "source_group": "B"},
    {"id": "...", "reason": "...", "is_hot_duplicate": false, "source_group": "C"}
  ],
  "alternates": [
    {"id": "...", "reason": "..."},
    {"id": "...", "reason": "..."},
    {"id": "...", "reason": "..."}
  ]
}"""


def _strip_code_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()
    return s


def _host(url: str | None) -> str:
    if not url:
        return ""
    try:
        h = urlparse(url).netloc.lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


def _format_user_message(candidates: list[dict]) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines: list[str] = [f"Today: {today}.", ""]
    groups: dict[str, list[dict]] = {"A": [], "B": [], "C": []}
    for c in candidates:
        g = c.get("discovery_group") or ""
        if g in groups:
            groups[g].append(c)

    labels = {
        "A": "GROUP A (Tier 1 — NPR, Reuters)",
        "B": "GROUP B (Tier 2 — AP, BBC, Guardian)",
        "C": "GROUP C (RSS — PBS NewsHour)",
    }
    for key in ("A", "B", "C"):
        lines.append(labels[key] + ":")
        if not groups[key]:
            lines.append("  (none)")
            lines.append("")
            continue
        for c in groups[key]:
            title = (c.get("title") or "").strip()
            host = c.get("source_name") or _host(c.get("source_url"))
            snippet = (c.get("snippet") or "").strip().replace("\n", " ")
            if len(snippet) > 400:
                snippet = snippet[:400] + "..."
            lines.append(f"[id: {c.get('id')}] {title}")
            lines.append(f"  host: {host}")
            lines.append(f"  snippet: {snippet}")
        lines.append("")
    lines.append("Now return the curator JSON per the rules.")
    return "\n".join(lines)


def _call_deepseek_curator(user_message: str, api_key: str) -> tuple[dict, dict]:
    body = {
        "model": cfg.DEEPSEEK_MODEL,
        "temperature": 0.2,
        "max_tokens": 1500,
        "messages": [
            {"role": "system", "content": CURATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    r = requests.post(cfg.DEEPSEEK_ENDPOINT, headers=headers, json=body, timeout=90)
    r.raise_for_status()
    full = r.json()
    content = full["choices"][0]["message"]["content"]
    cleaned = _strip_code_fences(content)
    parsed = json.loads(cleaned)
    return parsed, full


def _validate_and_fix_picks(
    parsed: dict,
    candidates: list[dict],
) -> tuple[dict, list[str]]:
    """Enforce hard rules R1/R2/R3 server-side. Returns (fixed_parsed, warnings)."""
    warnings: list[str] = []
    by_id: dict[str, dict] = {c["id"]: c for c in candidates}
    rss_candidates = [c for c in candidates if c.get("discovery_group") == "C"]
    picks_raw = parsed.get("picks") or []
    alternates_raw = parsed.get("alternates") or []

    # Keep only picks with valid ids present in candidates
    picks: list[dict] = []
    used_ids: set[str] = set()
    used_hosts: set[str] = set()
    for p in picks_raw:
        pid = p.get("id")
        if not pid or pid in used_ids or pid not in by_id:
            continue
        cand = by_id[pid]
        host = cand.get("source_name") or _host(cand.get("source_url"))
        # R3 partial enforcement — skip if host already used AND we already have
        # a Group-C pick satisfying R2 (we'll fix missing host-duplication later).
        picks.append({**p, "_host": host, "_cand": cand})
        used_ids.add(pid)
        used_hosts.add(host)

    # Trim to first 3 valid ones for now
    picks = picks[:3]

    # R1: pad to 3 using alternates + remaining candidates if needed
    def _try_add_pick(cand: dict, reason: str, is_hot: bool, source_group: str) -> bool:
        h = cand.get("source_name") or _host(cand.get("source_url"))
        if cand["id"] in used_ids:
            return False
        if h in used_hosts:
            return False
        picks.append({
            "id": cand["id"],
            "reason": reason,
            "is_hot_duplicate": is_hot,
            "source_group": source_group,
            "_host": h,
            "_cand": cand,
        })
        used_ids.add(cand["id"])
        used_hosts.add(h)
        return True

    def _force_add_pick(cand: dict, reason: str, is_hot: bool, source_group: str) -> None:
        h = cand.get("source_name") or _host(cand.get("source_url"))
        picks.append({
            "id": cand["id"],
            "reason": reason,
            "is_hot_duplicate": is_hot,
            "source_group": source_group,
            "_host": h,
            "_cand": cand,
        })
        used_ids.add(cand["id"])
        used_hosts.add(h)

    # R3 dedup among existing picks — drop duplicates-by-host, keep first
    deduped: list[dict] = []
    seen_hosts: set[str] = set()
    for p in picks:
        if p["_host"] in seen_hosts:
            warnings.append(f"dropping duplicate-host pick {p['id']} host={p['_host']}")
            used_ids.discard(p["id"])
            continue
        deduped.append(p)
        seen_hosts.add(p["_host"])
    picks = deduped
    used_hosts = seen_hosts

    # R2: if RSS (Group C) exists but no Group-C pick, force-swap weakest non-C pick
    rss_in_picks = any(
        (p.get("_cand") or {}).get("discovery_group") == "C" for p in picks
    )
    if rss_candidates and not rss_in_picks:
        # Pick "best" RSS candidate by longest snippet (per spec heuristic)
        def _snip_len(c: dict) -> int:
            return len(c.get("snippet") or "")
        best_rss = max(rss_candidates, key=_snip_len)
        warnings.append(
            f"R2 violation: curator omitted Group C; force-swapping "
            f"weakest non-C pick with best RSS candidate id={best_rss['id']}"
        )
        if picks:
            # Remove the last (weakest) pick
            dropped = picks.pop()
            used_ids.discard(dropped["id"])
            used_hosts.discard(dropped["_host"])
        _force_add_pick(
            best_rss,
            reason="[force-swap] R2: no Group C pick present; swapped in best RSS by snippet length",
            is_hot=False,
            source_group="C",
        )

    # R1: if still fewer than 3, pad from alternates, then remaining candidates
    if len(picks) < 3:
        for alt in alternates_raw:
            if len(picks) >= 3:
                break
            aid = alt.get("id")
            if not aid or aid not in by_id or aid in used_ids:
                continue
            c = by_id[aid]
            grp = c.get("discovery_group") or "?"
            _try_add_pick(
                c,
                reason=f"[promoted alternate] {alt.get('reason') or ''}",
                is_hot=False,
                source_group=grp,
            )

    if len(picks) < 3:
        # Final pad from any remaining candidate (different host)
        for c in candidates:
            if len(picks) >= 3:
                break
            if c["id"] in used_ids:
                continue
            grp = c.get("discovery_group") or "?"
            _try_add_pick(
                c,
                reason="[backfill pad] ensuring 3 picks",
                is_hot=False,
                source_group=grp,
            )

    # Alternates: keep only valid ones not already in picks
    alternates: list[dict] = []
    for alt in alternates_raw:
        aid = alt.get("id")
        if not aid or aid not in by_id or aid in used_ids:
            continue
        alternates.append({
            "id": aid,
            "reason": alt.get("reason") or "",
        })

    # Strip internal helpers
    clean_picks = [
        {
            "id": p["id"],
            "reason": p.get("reason") or "",
            "is_hot_duplicate": bool(p.get("is_hot_duplicate")),
            "source_group": p.get("source_group")
                or (p.get("_cand") or {}).get("discovery_group")
                or "?",
        }
        for p in picks
    ]

    duplicates = parsed.get("duplicates") or []
    if not isinstance(duplicates, list):
        duplicates = []

    return {
        "duplicates": duplicates,
        "picks": clean_picks,
        "alternates": alternates,
    }, warnings


def curate_news(candidates: list[dict], api_key: str) -> tuple[dict, int, list[str]]:
    """Run curator over candidates. Returns (curator_result, api_calls, warnings).

    curator_result shape: {"duplicates": [...], "picks": [...3...], "alternates": [...]}
    Picks are validated/enforced server-side for R1/R2/R3.
    """
    if not candidates:
        return {"duplicates": [], "picks": [], "alternates": []}, 0, ["no candidates to curate"]

    user_msg = _format_user_message(candidates)
    parsed: dict | None = None
    api_calls = 0
    last_err: Exception | None = None
    for attempt in (0, 1):
        try:
            api_calls += 1
            parsed, _full = _call_deepseek_curator(user_msg, api_key)
            break
        except Exception as e:
            last_err = e
            log.warning("Curator DeepSeek attempt %d failed: %s", attempt + 1, e)
            time.sleep(1.0 * (attempt + 1))
            parsed = None

    if parsed is None:
        log.error("Curator failed after retries: %s", last_err)
        # Fallback: build a default pick list respecting R1/R2/R3
        fake = {"duplicates": [], "picks": [], "alternates": []}
        fixed, warnings = _validate_and_fix_picks(fake, candidates)
        warnings.insert(0, f"curator_error: {last_err}")
        return fixed, api_calls, warnings

    fixed, warnings = _validate_and_fix_picks(parsed, candidates)
    return fixed, api_calls, warnings
