"""Pipeline checkpoint helpers — save state to Supabase after each major
stage so a failed run can resume mid-flow without re-paying upstream
LLM costs.

Storage:  table `redesign_checkpoints` (run_date, stage, data jsonb).
Resume:   set env `RESUME_FROM=<stage>`. The pipeline loads the
          matching checkpoint at startup and skips earlier stages.

Stages (in order):
    phase_a, stage1, stage2_picks, verify, rewrite, stage3_safety,
    enrich, persist

Source dataclass instances are dehydrated to (category, name) tuples
on save and rehydrated from the DB-driven source registry on load —
keeps the JSON portable and avoids pickling issues.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from .news_sources import NewsSource
from .supabase_io import client

log = logging.getLogger("checkpoint")

# Ordered list — used by `resume_from()` to compare positions.
STAGES = (
    "phase_a",         # after RSS fetch (briefs_by_cat)
    "stage1",          # after forbidden filter
    "stage2_picks",    # after curator (ranked_by_cat)
    "verify",          # after body+image verify (stories_by_cat)
    "rewrite",         # after rewrite (rewrites_by_cat)
    "stage3_safety",   # after safety filter + spare promotion
    "enrich",          # after detail enrich
    "persist",         # after Supabase persist
)


# ─────────────────────────────────────────────────────────────────────
# Source serialization helpers
# ─────────────────────────────────────────────────────────────────────
def _source_to_ref(src: NewsSource) -> dict:
    """Dehydrate a Source for JSON. Name+rss_url are the lookup keys
    when rehydrating; the rest is convenience metadata for inspection."""
    return {
        "_kind": "source_ref",
        "name": src.name,
        "rss_url": src.rss_url,
        "id": src.id,
    }


def _ref_to_source(ref: dict, source_lookup: dict[tuple[str, str], NewsSource]) -> NewsSource | None:
    """Look up a Source by (name, rss_url). Returns None if the source
    has been removed from the registry — caller must handle missing."""
    return source_lookup.get((ref.get("name", ""), ref.get("rss_url", "")))


def _is_source_ref(obj: Any) -> bool:
    return isinstance(obj, dict) and obj.get("_kind") == "source_ref"


def _walk_to_jsonable(obj: Any) -> Any:
    """Convert obj to JSON-safe form. Source objects → ref dicts."""
    if isinstance(obj, NewsSource):
        return _source_to_ref(obj)
    if isinstance(obj, dict):
        return {k: _walk_to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_walk_to_jsonable(x) for x in obj]
    if isinstance(obj, set):
        return [_walk_to_jsonable(x) for x in sorted(obj, key=str)]
    return obj


def _walk_from_jsonable(obj: Any, source_lookup: dict) -> Any:
    """Reverse of `_walk_to_jsonable`. Source refs → NewsSource."""
    if _is_source_ref(obj):
        s = _ref_to_source(obj, source_lookup)
        if s is None:
            log.warning("checkpoint: source '%s' not in current registry — dropping",
                        obj.get("name"))
        return s
    if isinstance(obj, dict):
        return {k: _walk_from_jsonable(v, source_lookup) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_from_jsonable(x, source_lookup) for x in obj]
    return obj


# ─────────────────────────────────────────────────────────────────────
# Save / load
# ─────────────────────────────────────────────────────────────────────
def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def save(stage: str, data: Any, run_date: str | None = None) -> None:
    """Upsert the checkpoint for (run_date, stage). Best-effort: a save
    failure is logged but not raised so the pipeline keeps moving."""
    if stage not in STAGES:
        raise ValueError(f"unknown checkpoint stage: {stage}")
    rd = run_date or _today()
    try:
        payload = _walk_to_jsonable(data)
        body = json.dumps(payload, ensure_ascii=False)
        sb = client()
        sb.table("redesign_checkpoints").upsert({
            "run_date": rd,
            "stage": stage,
            "data": payload,
            "size_bytes": len(body.encode("utf-8")),
        }, on_conflict="run_date,stage").execute()
        log.info("checkpoint saved: %s/%s (%d bytes)", rd, stage, len(body))
    except Exception as e:  # noqa: BLE001
        log.warning("checkpoint save failed for %s/%s: %s", rd, stage, e)


def load(stage: str, source_lookup: dict, run_date: str | None = None) -> Any:
    """Fetch the (run_date, stage) checkpoint and rehydrate Source refs.
    Raises if the row doesn't exist."""
    if stage not in STAGES:
        raise ValueError(f"unknown checkpoint stage: {stage}")
    rd = run_date or _today()
    sb = client()
    res = sb.table("redesign_checkpoints") \
        .select("data,size_bytes,created_at") \
        .eq("run_date", rd).eq("stage", stage).maybe_single().execute()
    row = res.data if res else None
    if not row:
        raise FileNotFoundError(f"no checkpoint at {rd}/{stage}")
    log.info("checkpoint loaded: %s/%s (%d bytes, saved %s)",
             rd, stage, row.get("size_bytes") or 0, row.get("created_at"))
    return _walk_from_jsonable(row["data"], source_lookup)


def has(stage: str, run_date: str | None = None) -> bool:
    rd = run_date or _today()
    sb = client()
    res = sb.table("redesign_checkpoints") \
        .select("run_date,stage", count="exact") \
        .eq("run_date", rd).eq("stage", stage).execute()
    return (res.count or 0) > 0


def resume_from() -> str | None:
    """Read RESUME_FROM env var; validate and return canonical stage name
    or None when not set / blank. Raises on unknown values to fail fast."""
    val = (os.environ.get("RESUME_FROM") or "").strip()
    if not val:
        return None
    if val not in STAGES:
        raise ValueError(
            f"invalid RESUME_FROM={val!r}; must be one of {STAGES}"
        )
    return val


def stage_index(stage: str) -> int:
    return STAGES.index(stage)


def should_skip(current_stage: str, resume_target: str | None) -> bool:
    """True if `current_stage` should be skipped because we're resuming
    from a later stage. (i.e. resume_target is later than current_stage.)"""
    if resume_target is None:
        return False
    return STAGES.index(current_stage) <= STAGES.index(resume_target) - 1


# ─────────────────────────────────────────────────────────────────────
# Source-lookup builder
# ─────────────────────────────────────────────────────────────────────
def build_source_lookup(*source_lists) -> dict[tuple[str, str], NewsSource]:
    """Flatten a series of [Source, ...] lists into a {(name, rss_url): Source}
    map for rehydration."""
    out: dict[tuple[str, str], NewsSource] = {}
    for srcs in source_lists:
        for s in srcs or []:
            out[(s.name, s.rss_url)] = s
    return out
