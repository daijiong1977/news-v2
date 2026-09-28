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

# One taxonomy shared by routing and downstream category-fit scoring.
SECTION_POLICY = (
    "Editorial policy: animal science belongs in Science, including biology, animal research, "
    "new species, dinosaurs, animal fossils, behavior and ecology. Non-scientific animal "
    "stories such as pets, animal events and amusing wildlife activity belong in Fun. "
    "Technology and AI stories about public affairs belong in News: government use, "
    "regulation, civic consequences, infrastructure and data-center disputes, "
    "international negotiations, and effects on schools or communities. "
    "Playful technology and AI belong in Fun: robots, inventions, games, gadgets, "
    "creative uses and demonstrations whose main point is discovery or enjoyment. "
    "Technology research about underlying science may belong in Science. "
    "Judge the central subject, not incidental mentions: a chemistry study using an "
    "AI tool remains chemistry; a star discovery using a telescope remains astronomy; "
    "a new telescope instrument is technology. Science retains physics, chemistry, "
    "astronomy, Earth/climate science, plant/human biology, medicine and archaeology "
    "when animals are the scientific subject. News retains other current affairs, "
    "including major government and diplomatic developments even when the original "
    "article needs a child-friendly explanation. Fun also includes sports, music, "
    "film, games, arts, history and "
    "children's achievements. Classification never grants safety or publication approval."
)


def explicit_section(brief: dict) -> str | None:
    """An unambiguous sports article URL is Fun, not News.

    A football game mentioned incidentally in a politics article must remain
    eligible for News. This is a section hint, never a child-safety decision.
    """
    path = (urlsplit(brief.get("link") or brief.get("source_url") or "").path or "").lower()
    if path.startswith(("/sport/", "/sports/")):
        return "Fun"
    return None


def section_value(brief: dict) -> float | None:
    return (brief.get("_jev_rank") or {}).get("section_value")


def below_quality_floor(brief: dict) -> bool:
    """True only when Jev actually scored a brief below its section floor."""
    rank = brief.get("_jev_rank") or {}
    pick, floor = rank.get("editorial_pick"), rank.get("floor")
    return pick is not None and floor is not None and float(pick) < float(floor)


def low_fun_value(brief: dict) -> bool:
    value = section_value(brief)
    return value is not None and value <= 1.0


def important_news(brief: dict) -> bool:
    rank = brief.get("_jev_rank") or {}
    return (rank.get("section_value", 0) >= 2.5
            and rank.get("editorial_pick", rank.get("pick", 0)) >= rank.get("floor", .40)
            and rank.get("category_fit", 0) >= .60)


def news_editorial_strength(brief: dict) -> float | None:
    """Comparable News value for *already eligible* candidates.

    Topic and source variety are soft preferences; they should not displace a
    much stronger safe civic story. Missing JEV scores retain the old
    diversity-only ordering instead of being treated as zero-quality news.
    """
    rank = brief.get("_jev_rank") or {}
    pick = rank.get("editorial_pick")
    if pick is None:
        return None
    value = float(rank.get("section_value") or 0)
    global_rank = rank.get("global_rank")
    # The whole-set comparison carries information that isolated JEV scoring
    # misses, especially for timely civic explainers. It is a bounded signal,
    # never an eligibility or safety override.
    rank_bonus = (.02 * max(0, 6 - int(global_rank))
                  if isinstance(global_rank, int) and global_rank > 0 else 0)
    return float(pick) + .04 * min(4, max(0, value)) + rank_bonus


def prefer_important_news(items: list[dict], limit: int = 3) -> list[dict]:
    """Keep one qualified important story within already eligible/safe choices."""
    if any(important_news(x.get("brief") or {}) for x in items[:limit]):
        return items
    candidate = next((i for i, x in enumerate(items[limit:], limit)
                      if important_news(x.get("brief") or {})), None)
    if candidate is None:
        return items
    return items[:limit - 1] + [items[candidate]] + items[limit - 1:candidate] + items[candidate + 1:]


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


def prefer_final_editorial_diversity(category, items, limit=3):
    """Choose jointly; a later source-only pass must not undo topic diversity."""
    from .news_topics import topic_group
    n = min(limit, len(items))
    if n < 2:
        return items

    def quality(indices):
        chosen = [items[i] for i in indices]
        topics = {topic_group(x.get("brief") or {}) for x in chosen} - {""}
        publishers = {publisher_key(x.get("source")) for x in chosen} - {""}
        sources = {getattr(x.get("source"), "name", "") for x in chosen} - {""}
        important = category == "News" and any(important_news(x.get("brief") or {}) for x in chosen)
        science_publishers = min(SCIENCE_MIN_PUBLISHERS, len(publishers)) if category == "Science" else 0
        if category == "News":
            strengths = [news_editorial_strength(x.get("brief") or {}) for x in chosen]
            if all(s is not None for s in strengths):
                # One extra topic is worth 0.06, one extra feed 0.02; a
                # substantially stronger vetted story therefore remains in
                # the edition even when its broad topic repeats.
                score = sum(strengths) + .06 * len(topics) + .02 * len(sources)
                return (important, 0, round(score, 6), len(topics), len(sources),
                        -sum(indices), tuple(-i for i in indices))
        return (important, science_publishers, len(topics), len(publishers), len(sources),
                -sum(indices), tuple(-i for i in indices))

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
