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


def try_next_pick_for_source(phase_a_result: dict, already_used_ids: set[int]) -> dict | None:
    """Try the next non-used pick slot for a source (choice_2 or alternates)."""
    source = phase_a_result["source"]
    briefs = phase_a_result["kept_briefs"]
    # Build full attempt order again from batch_vet
    bv = phase_a_result["batch_vet"]
    vet_by_id = {v["id"]: v for v in bv.get("vet") or []}
    order: list[tuple[str, int]] = []
    for i, p in enumerate((bv.get("picks") or [])[:2]):
        order.append((f"choice_{i+1}", p.get("id")))
    for i, a in enumerate(bv.get("alternates") or []):
        order.append((f"alternate_{i}", a.get("id")))

    used_slot = phase_a_result.get("winner_slot")
    past_slot_used = False
    for slot, cid in order:
        if slot == used_slot:
            past_slot_used = True
            continue
        if not past_slot_used:
            continue
        if cid is None or cid >= len(briefs) or cid in already_used_ids:
            continue
        # Skip REJECTs
        v = vet_by_id.get(cid, {})
        if v.get("safety", {}).get("verdict") == "REJECT":
            continue
        art = dict(briefs[cid])
        if source.flow == "light" or not art.get("body"):
            log.info("[%s]  backfill fetching [%s id=%d]", source.name, slot, cid)
            art = _fetch_and_enrich(art)
        ok, reason = verify_article_content(art)
        if ok:
            art["_vet_info"] = v
            return {
                "source": source,
                "winner": art,
                "winner_slot": slot,
                "batch_vet": bv,
                "kept_briefs": briefs,
                "attempts": phase_a_result["attempts"] + [{"slot": slot, "id": cid, "ok": True, "reason": None}],
            }
    return None


def run_source(source: NewsSource) -> dict | None:
    """Single-pass source run. No backup-swap fallback (Q1=b — backup
    pool folded into primaries via cadence-aware scheduling)."""
    return run_source_phase_a(source)
