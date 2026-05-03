"""Pipeline configuration loaders that read from Supabase tables.

Phase 2 of the v2 admin: pipeline reads its categories, source registry,
and AI providers from DB rows that the admin page can edit, instead of
hardcoded Python literals.

  load_categories()           → [{slug, name, emoji, color, display_order}, ...]
  load_sources(category)      → [NewsSource, ...]   (matches news_sources.NewsSource shape)
  load_provider(role='any')   → Provider | None     (lowest-priority enabled match)

All three are read once at pipeline startup and cached on the module.
The admin page can edit the rows; changes take effect on the next run.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .news_sources import NewsSource
from .supabase_io import client

log = logging.getLogger("db-config")

# ─────────────────────────────────────────────────────────────────────────
# Caches — populated on first call, invalidated on process restart only.
# ─────────────────────────────────────────────────────────────────────────
_cat_cache: list[dict] | None = None
_src_cache: dict[str, list[NewsSource]] | None = None
_provider_cache: list["Provider"] | None = None


@dataclass
class Provider:
    """LLM provider config row from `redesign_ai_providers`."""
    id: str
    name: str
    base_url: str
    model_id: str
    api_key_env: str       # name of env var holding the key
    role: str              # 'curator' | 'rewriter' | 'enricher' | 'any'
    enabled: bool
    priority: int
    max_tokens_default: int | None
    temperature_default: float | None

    @property
    def api_key(self) -> str:
        """Resolve the key from env at call time. Raises if unset."""
        v = os.environ.get(self.api_key_env, "")
        if not v:
            raise RuntimeError(
                f"Provider {self.name}: env var {self.api_key_env} is empty / unset"
            )
        return v


# ─────────────────────────────────────────────────────────────────────────
# Categories
# ─────────────────────────────────────────────────────────────────────────
def load_categories() -> list[dict]:
    """Active categories ordered by display_order. Cached."""
    global _cat_cache
    if _cat_cache is not None:
        return _cat_cache
    sb = client()
    res = sb.table("redesign_categories") \
        .select("slug,name,emoji,color,display_order") \
        .eq("active", True) \
        .order("display_order") \
        .execute()
    _cat_cache = res.data or []
    log.info("loaded %d active categories from DB: %s",
             len(_cat_cache), [c["name"] for c in _cat_cache])
    return _cat_cache


# ─────────────────────────────────────────────────────────────────────────
# Sources
# ─────────────────────────────────────────────────────────────────────────
def _row_to_source(row: dict) -> NewsSource:
    """Map a redesign_source_configs row into the NewsSource dataclass
    consumed throughout the pipeline. The shape was deliberately mirrored
    when the table was first introduced (see seed_source_configs.py)."""
    return NewsSource(
        id=int(row["id"]),
        name=row["name"],
        rss_url=row["rss_url"],
        flow=row.get("flow") or "light",
        max_to_vet=int(row.get("max_to_vet") or 10),
        min_body_words=int(row.get("min_body_words") or 300),
        priority=int(row.get("priority") or 99),
        enabled=bool(row.get("enabled") if row.get("enabled") is not None else True),
        is_backup=bool(row.get("is_backup") or False),
        notes=row.get("notes") or "",
        feed_kind=row.get("feed_kind") or "rss",
        feed_config=row.get("feed_config"),
    )


def _ensure_src_cache() -> dict[str, list[dict]]:
    """One round-trip; cache the raw rows grouped by category."""
    global _src_cache
    if _src_cache is not None:
        # _src_cache stores NewsSource objects, not raw rows. Reload raw.
        pass
    sb = client()
    res = sb.table("redesign_source_configs").select("*").execute()
    rows = res.data or []
    by_cat: dict[str, list[dict]] = {}
    for r in rows:
        by_cat.setdefault((r.get("category") or "").strip(), []).append(r)
    return by_cat


def load_sources(category_name: str, *, today_weekday: int | None = None) -> list[NewsSource]:
    """Enabled non-backup sources for `category_name`, ordered for LRU rotation.

    Selection rules (in order):
      1. enabled = true
      2. is_backup = false
      3. ORDER BY last_used_at NULLS FIRST, priority ASC
         → least-recently-used sources surface first, breaking ties by
         the manual priority column. Pipeline downstream usually picks
         the top N from this list (max_per_source × N), so rotation
         emerges naturally — never picks the same source two days in a
         row when there are alternates available.

    Note: `today_weekday` is kept for back-compat but no longer affects
    selection. Earlier versions had a per-source `active_weekdays` pin
    ("Sports only on weekends"); we removed it to cut maintenance —
    every category is expected to keep ≥3 evergreen sources, and the
    LRU sort is enough rotation by itself.
    """
    global _src_cache
    if _src_cache is None:
        raw_by_cat = _ensure_src_cache()
        out: dict[str, list[NewsSource]] = {}
        for cat, rows in raw_by_cat.items():
            kept: list[tuple[str, int, NewsSource]] = []  # (last_used_iso_or_blank, priority, src)
            for r in rows:
                if not r.get("enabled"): continue
                if r.get("is_backup"):  continue
                # Sourcefinder mining engine (separate repo) writes
                # candidates with state='probation' to this table.
                # Skip anything that isn't fully promoted to live.
                # state column may be missing on older rows — treat
                # NULL as 'live' for backwards compat.
                state = r.get("state")
                if state is not None and state != "live": continue
                last_used = r.get("last_used_at") or ""   # NULL → "" sorts before any iso string
                pri = int(r.get("priority") or 99)
                kept.append((last_used, pri, _row_to_source(r)))
            # Sort primarily by last_used_at (asc, NULL/blank first = least-recently-used);
            # break ties by manual priority.
            kept.sort(key=lambda t: (t[0], t[1]))
            out[cat] = [s for _, _, s in kept]
        _src_cache = out
    return _src_cache.get(category_name, [])


def load_backup_sources(category_name: str) -> list[NewsSource]:
    raw_by_cat = _ensure_src_cache()
    rows = [r for r in raw_by_cat.get(category_name, []) if r.get("is_backup")]
    rows.sort(key=lambda r: int(r.get("priority") or 99))
    return [_row_to_source(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────────
# AI Providers
# ─────────────────────────────────────────────────────────────────────────
def _ensure_provider_cache() -> list[Provider]:
    global _provider_cache
    if _provider_cache is not None:
        return _provider_cache
    sb = client()
    res = sb.table("redesign_ai_providers") \
        .select("*") \
        .eq("enabled", True) \
        .order("priority") \
        .execute()
    out: list[Provider] = []
    for r in res.data or []:
        out.append(Provider(
            id=str(r["id"]),
            name=r["name"],
            base_url=r["base_url"].rstrip("/"),
            model_id=r["model_id"],
            api_key_env=r["api_key_secret"],
            role=r.get("role") or "any",
            enabled=bool(r.get("enabled")),
            priority=int(r.get("priority") or 100),
            max_tokens_default=r.get("max_tokens_default"),
            temperature_default=float(r["temperature_default"]) if r.get("temperature_default") is not None else None,
        ))
    _provider_cache = out
    log.info("loaded %d enabled AI providers from DB: %s",
             len(out), [(p.name, p.role) for p in out])
    return _provider_cache


def select_provider(role: str = "any") -> Optional[Provider]:
    """Return the lowest-priority enabled provider matching `role`,
    falling back to a `role='any'` match. None if no providers exist."""
    providers = _ensure_provider_cache()
    if not providers:
        return None
    matches = [p for p in providers if p.role == role]
    if not matches:
        matches = [p for p in providers if p.role == "any"]
    if not matches:
        return None
    return matches[0]   # already ordered by priority asc


def reset_caches() -> None:
    """Force re-load on next call (used by tests / long-running daemons)."""
    global _cat_cache, _src_cache, _provider_cache
    _cat_cache = None
    _src_cache = None
    _provider_cache = None
