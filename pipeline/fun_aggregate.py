"""Fun aggregator — mirrors science_aggregate.py but uses fun sources.

Per-weekday: 3 sources (topic-specific). BBC Tennis 3x/week (Tue/Sat/Sun).

Run:  python -m pipeline.fun_aggregate
View: http://localhost:18100/fun-today.html
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
log = logging.getLogger("fun-aggregate")


def title_excerpt(art: dict) -> str:
    body = art.get("body") or ""
    if not body:
        return (art.get("summary") or "")[:300]
    return body[:400]


def try_next_pick_for_source(phase_a_result, already_used_ids):
    source = phase_a_result["source"]
    briefs = phase_a_result["kept_briefs"]
    bv = phase_a_result["batch_vet"]
    vet_by_id = {v["id"]: v for v in bv.get("vet") or []}
    order = []
    for i, p in enumerate((bv.get("picks") or [])[:2]):
        order.append((f"choice_{i+1}", p.get("id")))
    for i, a in enumerate(bv.get("alternates") or []):
        order.append((f"alternate_{i}", a.get("id")))
    used_slot = phase_a_result.get("winner_slot")
    past = False
    for slot, cid in order:
        if slot == used_slot:
            past = True
            continue
        if not past or cid is None or cid >= len(briefs) or cid in already_used_ids:
            continue
        v = vet_by_id.get(cid, {})
        if v.get("safety", {}).get("verdict") == "REJECT":
            continue
        art = dict(briefs[cid])
        if source.flow == "light" or not art.get("body"):
            art = _fetch_and_enrich(art)
        # override verify thresholds: use source's min_body_words
        from .news_rss_core import is_generic_social_image
        wc = art.get("word_count", 0)
        if wc < source.min_body_words:
            continue
        if is_generic_social_image(art.get("og_image")) or not art.get("og_image"):
            continue
        art["_vet_info"] = v
        return {"source": source, "winner": art, "winner_slot": slot,
                "batch_vet": bv, "kept_briefs": briefs,
                "attempts": phase_a_result["attempts"] + [{"slot": slot, "id": cid, "ok": True, "reason": None}]}
    return None


def run_source(source):
    """Single-pass source run. No backup-swap fallback (Q1=b — backup
    pool folded into primaries via cadence-aware scheduling)."""
    return run_source_phase_a(source)
