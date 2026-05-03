"""News source registry.

Shaped to mirror the future Supabase table `redesign_news_sources`.
For now hardcoded here; migrate to Supabase in Phase 3 per
docs/superpowers/plans/2026-04-23-news-sources-supabase-migration.md
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

    @property
    def is_light(self) -> bool:
        return self.flow == "light"


SOURCES: list[NewsSource] = [
    NewsSource(
        id=2, name="PBS NewsHour",
        rss_url="https://www.pbs.org/newshour/feeds/rss/headlines",
        flow="full", max_to_vet=6, min_body_words=500,
        priority=1, enabled=True, is_backup=False,
        notes="cap at 6 to vetter",
    ),
    NewsSource(
        id=3, name="NPR World",
        rss_url="https://feeds.npr.org/1003/rss.xml",
        flow="light", max_to_vet=10, min_body_words=500,
        priority=2, enabled=True, is_backup=False,
    ),
    NewsSource(
        id=1, name="Al Jazeera",
        rss_url="https://www.aljazeera.com/xml/rss/all.xml",
        flow="full", max_to_vet=10, min_body_words=500,
        priority=3, enabled=True, is_backup=False,
    ),
    # Backups — Guardian World dropped per user (logo overlay on images).
    NewsSource(
        id=5, name="BBC News",
        rss_url="http://feeds.bbci.co.uk/news/rss.xml",
        flow="light", max_to_vet=25, min_body_words=500,
        priority=4, enabled=False, is_backup=True,
    ),
    NewsSource(
        id=6, name="ScienceDaily Top Technology",
        rss_url="https://www.sciencedaily.com/rss/top/technology.xml",
        flow="full", max_to_vet=25, min_body_words=500,
        priority=5, enabled=False, is_backup=True,
        notes="SD tech topic — news backup",
    ),
    NewsSource(
        id=7, name="ScienceDaily Strange & Offbeat",
        rss_url="https://www.sciencedaily.com/rss/strange_offbeat.xml",
        flow="full", max_to_vet=25, min_body_words=500,
        priority=6, enabled=False, is_backup=True,
        notes="SD offbeat — kid-wow backup",
    ),
    NewsSource(
        id=8, name="ScienceDaily Most Popular",
        rss_url="https://www.sciencedaily.com/rss/most_popular.xml",
        flow="full", max_to_vet=25, min_body_words=500,
        priority=7, enabled=False, is_backup=True,
        notes="SD most-popular — generic backup",
    ),
]


def enabled_sources() -> list[NewsSource]:
    return sorted([s for s in SOURCES if s.enabled and not s.is_backup],
                  key=lambda s: s.priority)


def backup_sources() -> list[NewsSource]:
    return sorted([s for s in SOURCES if s.is_backup],
                  key=lambda s: s.priority)
