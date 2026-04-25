"""Stage 1 of the mega pipeline: cheap deterministic forbidden-word filter
on RSS title + summary. Runs BEFORE any LLM call so we never spend tokens
on content that's clearly inappropriate for ages 8-13.

Designed for kids news. Not a full content-policy engine — just the
obvious nopes that never belong in a kids edition. Patterns are word-
boundary-anchored regexes; case-insensitive.

LLM safety vetting in Stage 3 catches subtler issues (sarcasm, context,
multi-word phrasing) on the REWRITTEN body.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger("forbidden")

# Patterns are intentionally conservative — kid-news editors prefer false
# positives (drop one borderline article) over false negatives (ship one
# inappropriate one). Each pattern is a regex run against lowercased
# title+summary with word boundaries.
#
# Categories:
#   · self-harm / suicide
#   · sexual abuse / assault
#   · graphic violence
#   · hard drugs (when used as nouns; medical-context safe due to phrasing)
#   · slurs (intentionally not enumerated here — extend the SLURS file
#     locally if needed; we don't ship a list to avoid normalizing them)
FORBIDDEN_PATTERNS: list[str] = [
    # ─── Self-harm / suicide ───
    r"\bsuicid(?:e|al|es|ed)\b",
    r"\bself[-\s]?harm(?:ed|ing)?\b",
    r"\bcutting\s+(?:themselves|themself|herself|himself)\b",

    # ─── Sexual abuse / assault ───
    r"\brape[ds]?\b",
    r"\braping\b",
    r"\bmolest(?:ed|er|ation|ing)?\b",
    r"\bsex(?:ual)?\s+(?:abuse|assault|predator|misconduct|harass(?:ment)?)\b",
    r"\bchild\s+(?:abuse|porn(?:ography)?)\b",
    r"\bgrooming\b(?!\s+(?:standards?|services?|tips?))",  # exempt pet/personal grooming

    # ─── Sexual content & online-predator slang ───
    r"\b(?:naked|nude|nudity|nudes)\b",
    r"\bx-?rated\b",
    r"\bsexting\b",
    r"\bsex\s+tape\b",
    r"\bporn(?:ography|ographic)?\b",
    r"\bonlyfans\b",
    r"\b(?:erotic|erotica|obscene|obscenity|obscenities)\b",
    r"\b(?:gnoc|cd9|asl)\b",          # predator slang acronyms

    # ─── Graphic violence ───
    r"\bbeheaded?\b",
    r"\bdismember(?:ed|ing|ment)?\b",
    r"\bmutilat(?:ed|ion|ing)?\b",
    r"\btortur(?:ed|ing|e)\b",
    r"\bmassacre(?:s|d)?\b",
    r"\bgang\s+rape\b",

    # ─── Active mass-violence ───
    r"\bschool\s+shoot(?:ing|er|ers)\b",
    r"\bmass\s+shoot(?:ing|er|ers)\b",
    r"\bactive\s+shoot(?:ing|er)\b",

    # ─── Hate / extremism / hate groups ───
    r"\bextremis(?:m|t|ts)\b",
    r"\bn[a@]z(?:i|is|ism)\b",         # nazi variants (incl. n@zi)
    r"\bneo[-\s]?n[a@]zi[s]?\b",
    r"\bswastik(?:a|as)\b",
    r"\bracist\b",
    r"\bhate\s+(?:speech|crime|crimes|group|groups)\b",
    r"\bwhite\s+(?:power|supremac(?:y|ist|ists))\b",
    r"\b(?:kkk|ku\s+klux\s+klan)\b",
    r"\bskinhead[s]?\b",
    r"\b(?:isis|al[-\s]?qaeda|taliban)\b",  # named terror orgs

    # ─── Hard drugs (noun usage, drug-bust contexts) ───
    r"\b(?:fentanyl|heroin|cocaine|methamphetamine|crystal\s+meth)\b",
    r"\boverdose[ds]?\b",
    r"\bdied\s+from\s+(?:drugs|overdose|fentanyl|heroin)\b",

    # ─── Gambling ───
    # Per editorial decision: kid news shouldn't normalize betting culture.
    # Trade-off: legitimate political/legal stories about gambling regulation
    # (e.g. Kalshi prediction-market enforcement) get filtered too. Acceptable.
    r"\b(?:betting|gambling|gambler[s]?|gamble[ds]?)\b",
    r"\bcasino[s]?\b",
    r"\b(?:slot\s+machine[s]?|slots)\b",
    r"\bloot\s+box(?:es)?\b",
    r"\bsports\s+book(?:s)?\b",
    r"\bonline\s+poker\b",
    r"\bprediction\s+market[s]?\b",
]

# Compile once at import time
_COMPILED = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_PATTERNS]


def is_forbidden(text: str) -> tuple[bool, str | None]:
    """Returns (forbidden?, matched_pattern_or_None). Empty text → not forbidden."""
    if not text:
        return False, None
    for pat in _COMPILED:
        m = pat.search(text)
        if m:
            return True, pat.pattern
    return False, None


def filter_briefs(briefs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split briefs into (kept, rejected). Each brief is expected to have
    `title` and `summary` keys (RSS-shape). Rejection is logged with the
    matched pattern so triage is easy."""
    kept: list[dict] = []
    rejected: list[dict] = []
    for b in briefs:
        scan_text = ((b.get("title") or "") + " " + (b.get("summary") or ""))
        bad, pat = is_forbidden(scan_text)
        if bad:
            log.info("  forbidden-filter DROP: pattern=%s · title=%s",
                     pat, (b.get("title") or "")[:80])
            rejected.append({**b, "_forbidden_pattern": pat})
        else:
            kept.append(b)
    return kept, rejected
