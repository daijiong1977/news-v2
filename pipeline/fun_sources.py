"""Fun source registry — 3 feeds per day, BBC Tennis 3x/week (Tue/Sat/Sun).

Shaped to mirror the future Supabase `redesign_fun_sources` table.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .news_sources import NewsSource


# BBC Tennis — user's favorite, appears Tue / Sat / Sun.
# min_body_words lowered to 150 since BBC Sport summaries are often short.
BBC_TENNIS = NewsSource(
    id=200, name="BBC Tennis",
    rss_url="https://feeds.bbci.co.uk/sport/tennis/rss.xml",
    flow="full", max_to_vet=10, min_body_words=150,
    priority=2, enabled=True, is_backup=False,
    notes="user favorite · 3x/week (Tue/Sat/Sun)",
)


WEEKDAY_TOPICS: dict[int, str] = {
    0: "Music",
    1: "Swimming / Water sports (+ tennis)",
    2: "Movies / TV",
    3: "Cool inventions / kid inventors / new toys",
    4: "Arts / Crafts",
    5: "Animals / Famous person / History (+ tennis)",
    6: "Video games / Esports (+ tennis)",
}


# Per-weekday 3-source config. Key = datetime.weekday() 0=Mon ... 6=Sun.
# Each tuple: (source 1, source 2, source 3)
WEEKDAY_SOURCES: dict[int, list[NewsSource]] = {
    # Mon — Music
    0: [
        NewsSource(id=210, name="NPR Music",
                   rss_url="https://feeds.npr.org/1039/rss.xml",
                   flow="light", max_to_vet=10, min_body_words=300,
                   priority=1, enabled=True, is_backup=False),
        NewsSource(id=211, name="Rolling Stone Music",
                   rss_url="https://www.rollingstone.com/music/feed/",
                   flow="full", max_to_vet=10, min_body_words=300,
                   priority=2, enabled=True, is_backup=False),
        NewsSource(id=212, name="Billboard",
                   rss_url="https://www.billboard.com/feed/",
                   flow="full", max_to_vet=10, min_body_words=300,
                   priority=3, enabled=True, is_backup=False),
    ],
    # Tue — Swimming + TENNIS
    1: [
        NewsSource(id=220, name="SwimSwam",
                   rss_url="https://swimswam.com/feed/",
                   flow="full", max_to_vet=10, min_body_words=300,
                   priority=1, enabled=True, is_backup=False),
        BBC_TENNIS,
        NewsSource(id=221, name="Popular Mechanics",   # sport+gear fallback
                   rss_url="https://www.popularmechanics.com/rss/all.xml",
                   flow="full", max_to_vet=10, min_body_words=300,
                   priority=3, enabled=True, is_backup=False),
    ],
    # Wed — Movies / TV
    2: [
        NewsSource(id=230, name="Variety",
                   rss_url="https://variety.com/feed/",
                   flow="full", max_to_vet=10, min_body_words=300,
                   priority=1, enabled=True, is_backup=False),
        NewsSource(id=231, name="/Film",
                   rss_url="https://www.slashfilm.com/feed/",
                   flow="full", max_to_vet=10, min_body_words=300,
                   priority=2, enabled=True, is_backup=False),
        NewsSource(id=232, name="IndieWire",
                   rss_url="https://www.indiewire.com/feed/",
                   flow="full", max_to_vet=10, min_body_words=300,
                   priority=3, enabled=True, is_backup=False),
    ],
    # Thu — Inventions / kid inventors / toys
    3: [
        NewsSource(id=240, name="Wired Gear",
                   rss_url="https://www.wired.com/feed/category/gear/latest/rss",
                   flow="full", max_to_vet=10, min_body_words=300,
                   priority=1, enabled=True, is_backup=False),
        NewsSource(id=241, name="Popular Mechanics",
                   rss_url="https://www.popularmechanics.com/rss/all.xml",
                   flow="full", max_to_vet=10, min_body_words=300,
                   priority=2, enabled=True, is_backup=False),
        NewsSource(id=242, name="MIT News",
                   rss_url="https://news.mit.edu/rss/feed",
                   flow="full", max_to_vet=10, min_body_words=300,
                   priority=3, enabled=True, is_backup=False),
    ],
    # Fri — Arts / Crafts
    4: [
        NewsSource(id=250, name="Smithsonian Arts",
                   rss_url="https://www.smithsonianmag.com/rss/arts-culture/",
                   flow="full", max_to_vet=10, min_body_words=300,
                   priority=1, enabled=True, is_backup=False),
        NewsSource(id=251, name="Colossal",
                   rss_url="https://www.thisiscolossal.com/feed/",
                   flow="full", max_to_vet=10, min_body_words=300,
                   priority=2, enabled=True, is_backup=False,
                   notes="replaces Guardian Art & Design (logo overlay)"),
        NewsSource(id=252, name="Hyperallergic",
                   rss_url="https://hyperallergic.com/feed/",
                   flow="full", max_to_vet=10, min_body_words=300,
                   priority=3, enabled=True, is_backup=False),
    ],
    # Sat — Animals / Famous person / History + TENNIS
    5: [
        NewsSource(id=260, name="Smithsonian History",
                   rss_url="https://www.smithsonianmag.com/rss/history/",
                   flow="full", max_to_vet=10, min_body_words=300,
                   priority=1, enabled=True, is_backup=False),
        BBC_TENNIS,
        NewsSource(id=261, name="Live Science",
                   rss_url="https://www.livescience.com/feeds/all",
                   flow="full", max_to_vet=10, min_body_words=300,
                   priority=3, enabled=True, is_backup=False),
    ],
    # Sun — Video games / Esports + TENNIS
    6: [
        NewsSource(id=270, name="Polygon",
                   rss_url="https://www.polygon.com/rss/index.xml",
                   flow="full", max_to_vet=10, min_body_words=300,
                   priority=1, enabled=True, is_backup=False),
        NewsSource(id=271, name="Kotaku",
                   rss_url="https://kotaku.com/rss",
                   flow="full", max_to_vet=10, min_body_words=300,
                   priority=2, enabled=True, is_backup=False),
        BBC_TENNIS,
    ],
}


# Global backup pool
FUN_BACKUPS: list[NewsSource] = [
    NewsSource(id=280, name="Smithsonian Science-Nature",
               rss_url="https://www.smithsonianmag.com/rss/science-nature/",
               flow="full", max_to_vet=25, min_body_words=300,
               priority=9, enabled=False, is_backup=True),
    NewsSource(id=281, name="NPR Music (backup)",
               rss_url="https://feeds.npr.org/1039/rss.xml",
               flow="light", max_to_vet=25, min_body_words=300,
               priority=9, enabled=False, is_backup=True),
]


def todays_enabled_sources() -> list[NewsSource]:
    weekday = datetime.now(timezone.utc).weekday()
    return WEEKDAY_SOURCES[weekday]


def todays_topic() -> str:
    weekday = datetime.now(timezone.utc).weekday()
    return WEEKDAY_TOPICS[weekday]


def todays_backup_sources() -> list[NewsSource]:
    return FUN_BACKUPS
