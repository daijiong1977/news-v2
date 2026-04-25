"""Deterministic keyword extraction from rewritten article bodies.

Scans the rewritten body for "vocabulary-worthy" words: anything ranked
beyond a frequency threshold in the Google 10k English-frequency list,
or not in the list at all (proper nouns, technical terms, etc.).

  easy slot   → keep words with rank > 2000   ("crime" = rank 2000)
  middle slot → keep words with rank > 3000   ("encyclopedia" = rank 3000)

Output entries have NO explanation field — that step requires LLM or
dictionary lookup. This module is deterministic, fast, and produces
keywords that are guaranteed to appear in the body (no hallucinations).

Frequency list source: github.com/first20hours/google-10000-english
("no-swears" variant — appropriate for a kid-news site).
"""
from __future__ import annotations

import re
from pathlib import Path

_DATA_FILE = Path(__file__).parent / "data" / "google-10k-no-swears.txt"

# Lazy-loaded {lowercased word → rank (1-indexed, lower = more common)}.
_RANK: dict[str, int] = {}

# Tokens we never surface as keywords — capitalization or context alone
# isn't enough to make them interesting vocabulary for kids.
_STOPLIST: frozenset[str] = frozenset({
    # Days, months — common, not vocabulary
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
    # Pronouns + auxiliaries that survive the rank cut by being all-caps in headlines
    "what", "where", "when", "why", "how", "who",
    # Roman numerals + common abbreviations frequently mis-tokenized as words
    "iii", "iv", "vi", "vii", "viii", "ix", "xi", "xii",
    "etc", "vs", "via", "ie",
})

# Tokens are letter runs that may include apostrophes or hyphens. Numbers
# and symbols are dropped. Single letters are filtered later by length.
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")

# Below this length we don't surface a token (function words, common
# 3-letter words like "the/and/but" mostly captured by the freq list,
# but kid-readable single/short tokens are noise either way).
_MIN_TOKEN_LEN = 4

THRESHOLDS = {"easy": 2000, "middle": 3000}


def _ensure_loaded() -> None:
    if _RANK:
        return
    if not _DATA_FILE.is_file():
        raise FileNotFoundError(f"freq list not found: {_DATA_FILE}")
    with _DATA_FILE.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            word = line.strip().lower()
            if word and word not in _RANK:
                _RANK[word] = i


def word_rank(token: str) -> int | None:
    """Return rank (1=most common) or None if unranked."""
    _ensure_loaded()
    return _RANK.get(token.lower())


def extract_keywords(body: str, level: str, max_count: int = 8) -> list[dict]:
    """Scan rewritten body, return rank-filtered keyword terms.

    `level` must be "easy" or "middle". A token qualifies if its rank
    in the Google 10k list is above the level's threshold OR if it isn't
    in the list at all (proper nouns / technical terms).

    Each entry shape: {"term": <str>, "rank": <int or None>, "explanation": ""}.
    The explanation field is empty by design — fill it server-side later
    via dictionary lookup if/when desired. Order is first-appearance in
    body; capped at `max_count`.
    """
    if not body or level not in THRESHOLDS:
        return []
    _ensure_loaded()
    threshold = THRESHOLDS[level]
    seen: set[str] = set()
    out: list[dict] = []
    for m in _TOKEN_RE.finditer(body):
        original = m.group(0)
        lower = original.lower().strip("'-")  # trim trailing/leading punct
        if len(lower) < _MIN_TOKEN_LEN:
            continue
        if lower in seen or lower in _STOPLIST:
            continue
        seen.add(lower)
        rank = _RANK.get(lower)
        if rank is None or rank > threshold:
            out.append({
                "term": original,
                "rank": rank,
                "explanation": "",
            })
            if len(out) >= max_count:
                break
    return out


def augment_details_with_keywords(details: dict, rewrite_result: dict) -> dict:
    """Append Python-scanned keywords to each slot's keyword list.

    `details` shape: {"<source_id>_<level>": {"keywords": [...], ...}}.
    `rewrite_result` shape: {"articles": [{"source_id": int, "easy_en": {"body": str},
                                            "middle_en": {"body": str}, ...}, ...]}.

    For each slot we pull the matching body, extract Python keywords, and
    append any whose lowercased term isn't already present in the LLM
    keyword list (case-insensitive dedup). The LLM keywords keep their
    explanations; Python-added ones have empty explanations.
    """
    articles_by_id = {a["source_id"]: a for a in rewrite_result.get("articles") or []
                       if isinstance(a.get("source_id"), int)}
    for slot_key, det in details.items():
        try:
            aid_str, level = slot_key.rsplit("_", 1)
            aid = int(aid_str)
        except (ValueError, TypeError):
            continue
        if level not in THRESHOLDS:
            continue
        article = articles_by_id.get(aid) or {}
        variant = article.get(f"{level}_en") or {}
        body = variant.get("body") or ""
        if not body:
            continue
        existing = det.get("keywords") or []
        existing_lc = {(k.get("term") or "").lower() for k in existing}
        for kw in extract_keywords(body, level):
            if kw["term"].lower() in existing_lc:
                continue
            existing.append(kw)
            existing_lc.add(kw["term"].lower())
        det["keywords"] = existing
    return details
