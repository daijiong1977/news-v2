"""News aggregator — runs Phase A (per source), B (cross-source dedup), C (tri-variant rewrite).

Workflow:
  Phase A (serial): for each enabled source, mine RSS → vet → pick winner.
    Tries choice_1 → choice_2 → alternates until content-quality check passes.
    If a source yields no winner after all attempts, pulls from random backup source.
  Phase B (cross-source dedup): DeepSeek compares the 3 winners' titles+excerpts.
    If dup found, drop the weaker one (lower-priority source) → try its choice_2 →
    if still dup, pull from random backup.
  Phase C (batch rewrite): 1 DeepSeek call generates tri-variant output for each
    of the 3 stories: easy_en (170-210w), middle_en (320-350w), zh (300 汉字 summary).

Run:  python -m pipeline.news_aggregate
View: http://localhost:18100/news-today.html
"""
from __future__ import annotations

import html
import json
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from .news_rss_core import (
    MIN_PICK_BODY_WORDS,
    SAFETY_DIMS,
    SAFETY_SHORT,
    _fetch_and_enrich,
    apply_vet_thresholds,
    check_duplicates,
    run_source_phase_a,
    tri_variant_rewrite,
    verdict_class,
    verify_article_content,
)
from .news_sources import NewsSource
_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("aggregate")


def title_excerpt(art: dict) -> str:
    """First 200 chars of body for dup-check + render."""
    body = art.get("body") or ""
    if not body:
        return (art.get("summary") or "")[:300]
    return body[:400]

def run_source(source: NewsSource) -> dict | None:
    """Single-pass source run. No backup-swap fallback (Q1=b — backup
    pool folded into primaries via cadence-aware scheduling)."""
    return run_source_phase_a(source)
