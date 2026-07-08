"""Science aggregator — mirrors news_aggregate.py but uses science sources.

3 sources per day: ScienceDaily All + Science News Explores + weekday-specific
topic feed (MIT Tech Review / NPR Health / Space.com / Physics World / Guardian
Environment / IEEE Spectrum / Smithsonian).

The curator is told today's topic so it can slightly prefer on-topic picks.

Run:  python -m pipeline.science_aggregate
View: http://localhost:18100/science-today.html
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
    _fetch_and_enrich,
    check_duplicates,
    run_source_phase_a,
    tri_variant_rewrite,
    verdict_class,
    verify_article_content,
)
from .news_sources import NewsSource
_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sci-aggregate")


def title_excerpt(art: dict) -> str:
    body = art.get("body") or ""
    if not body:
        return (art.get("summary") or "")[:300]
    return body[:400]

def run_source(source):
    """Single-pass source run. No backup-swap fallback (Q1=b — backup
    pool folded into primaries via cadence-aware scheduling)."""
    return run_source_phase_a(source)
