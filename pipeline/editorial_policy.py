"""Shared editorial rules, independent of child-safety scoring.

Feed names are not publisher identities. Recruitment announcements are not
the sporting achievements the Fun section is intended to surface.
"""
from __future__ import annotations

import html
from itertools import combinations
import re
from urllib.parse import urlsplit

SCIENCE_MIN_PUBLISHERS = 2


def publisher_key(source) -> str:
    """Known brand aliases, otherwise the feed hostname (not a guessed eTLD)."""
    def get(key):
        return source.get(key, "") if isinstance(source, dict) else getattr(source, key, "")

    host = (urlsplit(get("rss_url") or "").hostname or "").lower().removeprefix("www.")
    for domain, brand in (("sciencedaily.com", "sciencedaily"),
                          ("bbc.co.uk", "bbc"), ("bbci.co.uk", "bbc"), ("bbc.com", "bbc"),
                          ("npr.org", "npr"), ("smithsonianmag.com", "smithsonian")):
        if host == domain or host.endswith("." + domain):
            return brand
    # Legacy/test/checkpoint sources can lack a URL. Group known ScienceDaily
    # feed names even then, rather than silently treating each as a publisher.
    name = (get("name") or "").strip().lower()
    if not host and name.startswith("sciencedaily"):
        return "sciencedaily"
    return host or name


def prefer_science_publishers(items: list[dict], limit: int = 3) -> list[dict]:
    """Reorder already-eligible items for two publishers, then topic diversity.

    Entries have source and brief fields. Never admits a new candidate or
    changes its scores; callers must apply their normal eligibility gates.
    """
    from .news_topics import topic_group

    n = min(limit, len(items))
    if n < 2 or len({publisher_key(x.get("source")) for x in items[:n]} - {""}) >= SCIENCE_MIN_PUBLISHERS:
        return items
    if len({publisher_key(x.get("source")) for x in items} - {""}) < SCIENCE_MIN_PUBLISHERS:
        return items

    def quality(indices):
        selected = [items[i] for i in indices]
        publishers = {publisher_key(x.get("source")) for x in selected} - {""}
        topics = {topic_group(x.get("brief") or {}) for x in selected} - {""}
        feeds = {getattr(x.get("source"), "name", "") for x in selected} - {""}
        return (min(SCIENCE_MIN_PUBLISHERS, len(publishers)), len(topics),
                len(feeds), -sum(indices), tuple(-i for i in indices))

    chosen = max(combinations(range(len(items)), n), key=quality)
    return [items[i] for i in chosen] + [x for i, x in enumerate(items) if i not in chosen]


_CONTEXT = re.compile(
    r"\b(?:ncaa|recruit\w*|swim\w*|"
    r"tennis|athlet\w*|basketball|football|soccer|volleyball|baseball|softball|"
    r"gymnast\w*|rowing|diving|track|wrestl\w*|class of 20\d\d)\b", re.I)
_RECRUITING = re.compile(
    r"\b(?:verbal(?:ly)?\s+commit\w*|recruiting|recruitment|signing day|"
    r"transfer portal|recruit\w*\s+(?:class\w*|rank\w*))\b|"
    r"\b(?:signs?|signed|signing)\b.{0,50}\b(?:letter of intent|scholarship)\b",
    re.I)
_COMMIT = re.compile(r"\bcommit(?:s|ted|ting|ment|ments)?\b.{0,80}\bto\b", re.I)
_COLLEGE = re.compile(r"\b(?:college|collegiate|universit\w*|ncaa|scholarship|"
                      r"recruit\w*|class of 20\d\d|for 20\d\d)\b", re.I)
_RESULT = re.compile(
    r"\b(?:breaks?|broke|sets?|wins?|won|claims?)\b.{0,55}"
    r"\b(?:record|title|championship|medal|final)\b", re.I)


def editorial_exclusion(article: dict) -> str | None:
    """Classify primary recruitment news, not incidental athlete biography.

    Applied to every input section so a misfiled News story cannot later route
    into Fun. Check the headline first; only inspect the lead for vague titles.
    A race/record headline with recruitment mentioned in background stays in.
    """
    clean = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()
    title = clean(article.get("title"))
    lead = clean(article.get("summary") or article.get("body"))[:500]
    context = bool(_CONTEXT.search(title + " " + lead + " " + (article.get("_source_name") or "")))
    def recruiting(text):
        return _RECRUITING.search(text) or (_COMMIT.search(text) and _COLLEGE.search(title + " " + lead))

    if context and recruiting(title):
        return "college_recruiting"
    if _RESULT.search(title):
        return None
    # Avoid scanning a full article: recruiting can be incidental background.
    opening = " ".join(re.split(r"(?<=[.!?])\s+", lead)[:2])
    if context and recruiting(opening):
        return "college_recruiting"
    return None
