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
        cadence_days=int(row.get("cadence_days") or 1),
        last_used_at=row.get("last_used_at"),
        next_pickup_at=row.get("next_pickup_at"),
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


def load_sources(category_name: str, *,
                 today: "date | None" = None,
                 n: int = 3) -> list[NewsSource]:
    """Cadence-aware source selection per category.

    See docs/superpowers/specs/2026-05-03-cadence-aware-source-selection-design.md
    for the full algorithm. Returns up to `n` sources, ordered by:
      next_pickup_at ASC NULLS FIRST, priority ASC, last_used_at ASC NULLS FIRST.

    Eligible (next_pickup_at IS NULL OR <= today) come first; if fewer than
    `n` are eligible, fill from closest-to-eligible (next_pickup_at > today,
    soonest first). The pool is exhausted before under-fill is accepted.
    `is_backup` is ignored — all enabled sources participate.
    """
    from datetime import date as _date
    if today is None:
        today = _date.today()

    raw_by_cat = _ensure_src_cache()
    rows = raw_by_cat.get(category_name, [])

    # Filter: enabled, state in (NULL, 'live'). is_backup ignored (Q1=b).
    candidates = [r for r in rows
                  if r.get("enabled")
                  and (r.get("state") in (None, "live"))]

    # Slice the first 10 chars (YYYY-MM-DD) so we compare dates, not
    # timestamps. next_pickup_at is currently DATE (PostgREST returns
    # 'YYYY-MM-DD'); last_used_at is stored as a full ISO timestamp via
    # full_round's stamp loop. Slicing makes the sort/eligibility checks
    # robust against either format AND against a future schema migration
    # to TIMESTAMPTZ on next_pickup_at.
    def _date_part(s):
        return (s or "")[:10]

    def _sort_key(r):
        npa = _date_part(r.get("next_pickup_at"))   # NULL/"" sorts first
        prio = int(r.get("priority") or 99)
        lua = _date_part(r.get("last_used_at"))
        return (npa, prio, lua)

    today_iso = today.isoformat()
    eligible = sorted(
        [r for r in candidates
         if not r.get("next_pickup_at") or _date_part(r["next_pickup_at"]) <= today_iso],
        key=_sort_key,
    )
    sleeping = sorted(
        [r for r in candidates
         if r.get("next_pickup_at") and _date_part(r["next_pickup_at"]) > today_iso],
        key=_sort_key,
    )

    picked = eligible[:n]
    if len(picked) < n:
        picked += sleeping[:n - len(picked)]

    return [_row_to_source(r) for r in picked]


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
