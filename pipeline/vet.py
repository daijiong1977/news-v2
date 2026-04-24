"""Step 2 — VET (Stage 1): DeepSeek safety scoring on title + snippet."""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

import requests

from . import config as cfg

log = logging.getLogger(__name__)


def _strip_code_fences(text: str) -> str:
    """DeepSeek sometimes wraps JSON in ```json ... ``` fences."""
    s = text.strip()
    if s.startswith("```"):
        # remove leading ``` and optional language tag
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        if s.endswith("```"):
            s = s[: -3]
        s = s.strip()
    return s


def _verdict_from_total(total: int) -> str:
    if total <= cfg.VET_SAFE_MAX:
        return "SAFE"
    if total <= cfg.VET_CAUTION_MAX:
        return "CAUTION"
    return "REJECT"


def _interest_verdict_from_peak(peak: int) -> str:
    if peak >= 3:
        return "ENGAGING"
    if peak == 2:
        return "MEH"
    return "BORING"


def _call_deepseek(title: str, snippet: str, api_key: str) -> tuple[dict, dict]:
    """Returns (parsed_json, raw_response_dict). Raises on network/parse failure."""
    body = {
        "model": cfg.DEEPSEEK_MODEL,
        "temperature": cfg.DEEPSEEK_TEMPERATURE,
        "max_tokens": cfg.DEEPSEEK_MAX_TOKENS,
        "messages": [
            {"role": "system", "content": cfg.VETTER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Title: {title}\nSnippet: {snippet}"},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    r = requests.post(cfg.DEEPSEEK_ENDPOINT, headers=headers, json=body, timeout=60)
    r.raise_for_status()
    full = r.json()
    content = full["choices"][0]["message"]["content"]
    cleaned = _strip_code_fences(content)
    parsed = json.loads(cleaned)
    return parsed, full


def vet_candidate(cand: dict, api_key: str) -> int:
    """Populates vet fields in-place. Returns number of DeepSeek API calls made."""
    title = cand.get("title", "")
    snippet = cand.get("snippet", "") or ""
    calls = 0
    last_err: Exception | None = None
    parsed: dict | None = None
    full: dict | None = None
    for attempt in (0, 1):
        try:
            calls += 1
            parsed, full = _call_deepseek(title, snippet, api_key)
            break
        except Exception as e:
            last_err = e
            log.warning("DeepSeek vet attempt %d failed for %s: %s", attempt + 1, title[:60], e)
            time.sleep(1.0 * (attempt + 1))
            parsed = None

    if parsed is None:
        cand["vetter_score"] = 40
        cand["vetter_verdict"] = "ERROR"
        cand["vetter_flags"] = ["vetter_error"]
        cand["vetter_payload"] = {"error": str(last_err) if last_err else "unknown"}
        cand["vetter_notes"] = f"Vetter error: {last_err}"
        cand["interest_scores"] = {"importance": 0, "fun_factor": 0, "kid_appeal": 0}
        cand["interest_peak"] = 0
        cand["interest_verdict"] = "BORING"
        return calls

    # ---- PART A: Safety ----
    # Accept both new (safety_scores/safety_total/safety_verdict) and legacy (scores/total/verdict) fields.
    safety_scores = parsed.get("safety_scores") or parsed.get("scores") or {}
    safety_total = parsed.get("safety_total")
    if safety_total is None:
        safety_total = parsed.get("total")
    if not isinstance(safety_total, (int, float)):
        try:
            safety_total = sum(int(v) for v in safety_scores.values() if isinstance(v, (int, float)))
        except Exception:
            safety_total = 0
    safety_total = int(safety_total)

    # Re-derive verdict from spec thresholds (authoritative) — don't trust the model's label.
    safety_verdict = _verdict_from_total(safety_total)

    # ---- PART B: Interest ----
    interest_scores_raw = parsed.get("interest_scores") or {}
    try:
        importance = int(interest_scores_raw.get("importance", 0) or 0)
    except Exception:
        importance = 0
    try:
        fun_factor = int(interest_scores_raw.get("fun_factor", 0) or 0)
    except Exception:
        fun_factor = 0
    try:
        kid_appeal = int(interest_scores_raw.get("kid_appeal", 0) or 0)
    except Exception:
        kid_appeal = 0
    interest_scores = {
        "importance": importance,
        "fun_factor": fun_factor,
        "kid_appeal": kid_appeal,
    }
    # Re-derive interest_peak from components (authoritative over the model's reported peak).
    interest_peak = max(importance, fun_factor, kid_appeal)
    interest_verdict = _interest_verdict_from_peak(interest_peak)

    flags = parsed.get("flags") or []
    if not isinstance(flags, list):
        flags = [str(flags)]

    # Backward-compatible: keep vetter_score=safety_total, vetter_verdict=safety_verdict.
    cand["vetter_score"] = safety_total
    cand["vetter_verdict"] = safety_verdict
    cand["vetter_flags"] = [str(f) for f in flags]
    cand["vetter_payload"] = parsed
    cand["vetter_payload_full"] = full  # for UI inspection (raw DeepSeek response)
    cand["vetter_notes"] = str(parsed.get("rewrite_notes") or "")
    # New interest fields.
    cand["interest_scores"] = interest_scores
    cand["interest_peak"] = interest_peak
    cand["interest_verdict"] = interest_verdict
    return calls


def _combined_rank_key(c: dict) -> tuple:
    """Sort key combining safety (asc), -interest_peak (asc = higher interest first),
    -tavily_score (asc = higher hotness first), and discovered_rank (tiebreak)."""
    safety_total = c.get("vetter_score") or 0
    interest_peak = c.get("interest_peak") or 0
    hotness = c.get("tavily_score") or 0
    discovered = c.get("discovered_rank") or 999
    return (safety_total, -interest_peak, -hotness, discovered)


def vet_candidates(candidates: list[dict], api_key: str) -> int:
    """Vets each candidate in-place. Assigns vetted_rank among SAFE/CAUTION survivors
    that also pass interest (not BORING). Returns total API calls.
    """
    total_calls = 0
    for c in candidates:
        total_calls += vet_candidate(c, api_key)

    # vetted_rank: rank (1..n) within SAFE+CAUTION AND non-BORING.
    survivors = [
        c for c in candidates
        if c.get("vetter_verdict") in {"SAFE", "CAUTION"}
        and c.get("interest_verdict") != "BORING"
    ]
    survivors.sort(key=_combined_rank_key)
    for i, c in enumerate(survivors, 1):
        c["vetted_rank"] = i

    return total_calls
