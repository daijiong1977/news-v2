"""Compare the JEV-qualified News catalog as a set before the six-item curator cut.

DeepSeek returns only a permutation of the numbered input. Titles and article
objects never come back from the model; they are resolved against this local
list. A malformed or failed response leaves the JEV shortlist untouched.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import Callable

from .editorial_policy import important_news
from .news_topics import topic_group

log = logging.getLogger("news-global-rank")

MAX_NEWS_COMPARISON = 30  # one numbered batch; deeper catalog stays for refill
NEWS_CURATOR_SLOTS = 6
NEWS_PICK_FLOOR = 0.40

SYSTEM_PROMPT = """You are choosing the order in which a children's NEWS editor
should review today's candidates. Readers are US children ages 10-14. Compare
the WHOLE numbered set, not one title at a time. Prefer concrete public events
that help children understand US civic life and elections, institutions and
rights, public-interest AI and technology, important diplomacy, and major world
developments. A useful civic explanation can matter even without a new law or
speech. A government agreement bringing pandas to a US zoo is a diplomatic and
cultural news event, not merely cute animal entertainment. Do not reward a
political party, dramatic language, or a famous name by itself.

Prefer three different real-world events, topics and publishers near the top.
Judge whether the source provides enough facts for a neutral, attributed rewrite;
do not reject politics, war, or civil rights merely because the subject is serious.
An explanation of how US elections are administered or checked can be more
valuable to children than routine campaign tactics or speculation about who
may win. Likewise, concrete government safeguards matter more than a famous
politician's opinion about them. Rank the actual public value of the event,
not the headline's drama or the outlet's prominence.
Put country profiles, sport, routine commentary, duplicate events and likely
repeats of the supplied seven-day published titles near the END. Do not invent
facts beyond the supplied title and summary.

Return ONLY a JSON array of ALL input numbers in best-to-worst order, each
number exactly once. No object, title, reason, markdown, or other text.
Example for four inputs: [3,1,4,2]"""


def _numbered_input(catalog: list[dict], recent_titles: list[str]) -> str:
    candidates = []
    for number, brief in enumerate(catalog, 1):
        summary = re.sub(r"<[^>]+>", " ", brief.get("summary") or "")
        candidates.append({"n": number, "title": brief.get("title") or "",
                           "source": brief.get("_source_name") or "",
                           "summary": " ".join(summary.split())[:250]})
    return json.dumps({"candidates": candidates,
                       "published_news_titles_prior_7d": recent_titles}, ensure_ascii=False)


def _valid_permutation(answer: object, count: int) -> bool:
    return (isinstance(answer, list) and len(answer) == count
            and all(type(n) is int for n in answer)
            and set(answer) == set(range(1, count + 1)))


def _choose_six(ordered: list[dict]) -> list[dict]:
    """Reserve one qualified major story, then honor source/topic breadth.

    Without this reservation, the first two stories from a publisher can
    consume its source cap before a later, more consequential story is seen.
    This is only a curator-input preference; body, history and safety gates
    still decide whether a story can be published.
    """
    major_pair = max(
        ((i, brief) for i, brief in enumerate(ordered) if important_news(brief)),
        key=lambda pair: (
            float(pair[1]["_jev_rank"]["section_value"]),
            float(pair[1]["_jev_rank"].get("editorial_pick", pair[1]["_jev_rank"].get("pick", 0))),
            -pair[0],
        ), default=None,
    )
    major = major_pair[1] if major_pair else None
    chosen: list[dict] = [major] if major is not None else []
    seen: set[int] = {id(major)} if major is not None else set()
    positions = {id(brief): i for i, brief in enumerate(ordered)}

    def in_rank_order() -> list[dict]:
        return sorted(chosen, key=lambda brief: positions[id(brief)])
    for source_cap, topic_cap, floor, known_topic in (
            (2, 2, NEWS_PICK_FLOOR, True),
            (2, None, NEWS_PICK_FLOOR, True),
            (2, None, NEWS_PICK_FLOOR, False),
            (3, None, NEWS_PICK_FLOOR, False),
            (None, None, None, False)):
        sources = Counter(b.get("_source_name") or "" for b in chosen)
        topics = Counter(topic_group(b) for b in chosen if topic_group(b))
        for brief in ordered:
            if len(chosen) == NEWS_CURATOR_SLOTS:
                return in_rank_order()
            if id(brief) in seen:
                continue
            rank = brief.get("_jev_rank") or {}
            if floor is not None and float(rank.get("editorial_pick") or 0) < floor:
                continue
            source = brief.get("_source_name") or ""
            topic = topic_group(brief)
            if known_topic and not topic:
                continue
            if source_cap is not None and sources[source] >= source_cap:
                continue
            if topic_cap is not None and topic and topics[topic] >= topic_cap:
                continue
            chosen.append(brief)
            seen.add(id(brief))
            sources[source] += 1
            if topic:
                topics[topic] += 1
    return in_rank_order()


def rerank_news_catalog(
    catalog: list[dict], recent_titles: list[str], *,
    call: Callable | None = None,
) -> tuple[list[dict], dict]:
    """Return a reordered full catalog and a small diagnostic report.

    The comparison input is capped at 29, but no existing catalog candidate is
    discarded. DeepSeek's order only decides review priority; all downstream
    curator, body, history and independent safety gates still apply.
    """
    count = min(len(catalog), MAX_NEWS_COMPARISON)
    report = {"status": "skipped", "compared": count, "sent": 0}
    if count < 2:
        return catalog, report
    if call is None:
        from .news_rss_core import deepseek_call
        call = deepseek_call
    try:
        answer = call(SYSTEM_PROMPT, _numbered_input(catalog[:count], recent_titles),
                      max_tokens=512, temperature=0.1, max_attempts=1,
                      json_mode=False)
        if not _valid_permutation(answer, count):
            raise ValueError("response is not a complete numeric permutation")
        ordered = [catalog[n - 1] for n in answer] + catalog[count:]
        chosen = _choose_six(ordered[:count])
        chosen_ids = {id(b) for b in chosen}
        for pos, brief in enumerate(ordered, 1):
            rank = brief.get("_jev_rank") or {}
            brief["_jev_rank"] = {**rank, "pos": pos, "send": id(brief) in chosen_ids,
                                   "global_rank": pos if pos <= count else None}
        report.update(status="applied", sent=len(chosen))
        log.info("News whole-catalog rank: compared %d, sent %d; top: %s",
                 count, len(chosen), answer[:10])
        return ordered, report
    except Exception as exc:  # optional editorial aid must not block publication
        log.warning("News whole-catalog rank ignored (%s); retaining JEV order", exc)
        report["status"] = "ignored"
        return catalog, report
