"""Science source registry — 3 per day:
  - 2 always-on (ScienceDaily All + Science News Explores)
  - 1 weekday-specific topic feed

Shaped to mirror the future Supabase `redesign_science_sources` table.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .news_sources import NewsSource


# Always-on sources (every day, priority 1 and 2)
SCIENCE_ALWAYS: list[NewsSource] = [
    NewsSource(
        id=101, name="ScienceDaily All",
        rss_url="https://www.sciencedaily.com/rss/all.xml",
        flow="full", max_to_vet=10, min_body_words=300,
        priority=1, enabled=True, is_backup=False,
        notes="breadth across all science",
    ),
    NewsSource(
        id=102, name="Science News Explores",
        rss_url="https://www.snexplores.org/feed",
        flow="full", max_to_vet=10, min_body_words=300,
        priority=2, enabled=True, is_backup=False,
        notes="kid-focused science writing (Society for Science)",
    ),
]


# Weekday-specific topic feed (priority 3). Key = weekday() 0=Mon ... 6=Sun.
# Avoids overlap with ScienceDaily All (no ScienceDaily subfeeds on day 3).
SCIENCE_WEEKDAY: dict[int, NewsSource] = {
    0: NewsSource(
        id=110, name="MIT Tech Review",
        rss_url="https://www.technologyreview.com/feed/",
        flow="full", max_to_vet=10, min_body_words=300,
        priority=3, enabled=True, is_backup=False,
        notes="Mon · AI / auto",
    ),
    1: NewsSource(
        id=111, name="NPR Health",
        rss_url="https://feeds.npr.org/1027/rss.xml",
        flow="light", max_to_vet=10, min_body_words=300,
        priority=3, enabled=True, is_backup=False,
        notes="Tue · Biology / Medicine / Health",
    ),
    2: NewsSource(
        id=112, name="Space.com",
        rss_url="https://www.space.com/feeds/all",
        flow="full", max_to_vet=10, min_body_words=300,
        priority=3, enabled=True, is_backup=False,
        notes="Wed · Space / Astronomy",
    ),
    3: NewsSource(
        id=113, name="Physics World",
        rss_url="https://physicsworld.com/feed/",
        flow="full", max_to_vet=10, min_body_words=300,
        priority=3, enabled=True, is_backup=False,
        notes="Thu · Chemistry / Physics (Physics World to avoid ScienceDaily subfeed overlap)",
    ),
    4: NewsSource(
        id=114, name="ScienceDaily Top Environment",
        rss_url="https://www.sciencedaily.com/rss/top/environment.xml",
        flow="full", max_to_vet=10, min_body_words=300,
        priority=3, enabled=True, is_backup=False,
        notes="Fri · Environment / Climate — replaces Guardian (logo overlay)",
    ),
    5: NewsSource(
        id=115, name="IEEE Spectrum",
        rss_url="https://spectrum.ieee.org/feeds/feed.rss",
        flow="full", max_to_vet=10, min_body_words=300,
        priority=3, enabled=True, is_backup=False,
        notes="Sat · Technology / Engineering",
    ),
    6: NewsSource(
        id=116, name="Smithsonian Science-Nature",
        rss_url="https://www.smithsonianmag.com/rss/science-nature/",
        flow="full", max_to_vet=10, min_body_words=300,
        priority=3, enabled=True, is_backup=False,
        notes="Sun · Nature / Geometry",
    ),
}

WEEKDAY_TOPICS: dict[int, str] = {
    0: "AI / auto",
    1: "Biology / Medicine / Health",
    2: "Space / Astronomy",
    3: "Chemistry / Physics",
    4: "Environment / Climate",
    5: "Technology / Engineering",
    6: "Nature / Geometry",
}


# Backup pool (used if a primary fails twice)
SCIENCE_BACKUPS: list[NewsSource] = [
    NewsSource(
        id=120, name="NASA News",
        rss_url="https://www.nasa.gov/news-release/feed/",
        flow="full", max_to_vet=25, min_body_words=300,
        priority=4, enabled=False, is_backup=True,
    ),
    NewsSource(
        id=121, name="Popular Science",
        rss_url="https://www.popsci.com/feed",
        flow="full", max_to_vet=25, min_body_words=300,
        priority=5, enabled=False, is_backup=True,
    ),
]


def todays_enabled_sources() -> list[NewsSource]:
    """Returns the 3 sources for today: 2 always-on + 1 weekday-specific."""
    weekday = datetime.now(timezone.utc).weekday()
    return SCIENCE_ALWAYS + [SCIENCE_WEEKDAY[weekday]]


def todays_topic() -> str:
    weekday = datetime.now(timezone.utc).weekday()
    return WEEKDAY_TOPICS[weekday]


def todays_backup_sources() -> list[NewsSource]:
    return SCIENCE_BACKUPS
