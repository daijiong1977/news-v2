"""News source dataclass.

The hardcoded SOURCES literal was decommissioned in Task 7 of
docs/superpowers/plans/2026-05-03-cadence-aware-source-selection.md;
sources are now loaded from `redesign_source_configs` via
`pipeline.db_config.load_sources`.

Only the `NewsSource` dataclass is kept here — it remains the in-memory
type used everywhere (db_config._row_to_source returns NewsSource
instances).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class NewsSource:
    id: int
    name: str
    rss_url: str
    flow: str                 # "full" | "light"
    max_to_vet: int
    min_body_words: int
    priority: int             # lower = primary
    enabled: bool
    is_backup: bool
    notes: str = ""
    feed_kind: str = "rss"          # rss | sitemap | html_list
    feed_config: str | None = None  # JSON; None for feed_kind='rss'
    cadence_days: int = 1                    # how many days between picks
    last_used_at: str | None = None          # ISO date string or None
    next_pickup_at: str | None = None        # ISO date string or None

    @property
    def is_light(self) -> bool:
        return self.flow == "light"
