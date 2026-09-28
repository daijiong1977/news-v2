"""Compare the JEV-qualified Fun catalog as a set before the curator cut.

DeepSeek returns a permutation of local numeric IDs, never rewritten titles.
Every candidate remains available for safe Stage-3 backfill. A bad or failed
response leaves JEV's ranking and shortlist untouched.
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import Callable

from .jev_rank import FLOOR, MIN_SEND, TO_CURATOR_BY_CATEGORY
from .news_global_rank import _valid_permutation
from .news_topics import topic_group

log = logging.getLogger("fun-global-rank")

MAX_FUN_COMPARISON = 30  # one numbered batch; deeper spares stay intact
FUN_CURATOR_SLOTS = TO_CURATOR_BY_CATEGORY["Fun"]
FUN_PICK_FLOOR = FLOOR["Fun"]

SYSTEM_PROMPT = """You are ranking today's FUN news candidates for US children
ages 10-14. Compare the WHOLE numbered list, not each headline alone. Prefer
real, recent, easy-to-retell events that children would genuinely enjoy:
major swimming or tennis records and championships, remarkable animal events,
creative inventions and playful technology, music, movies, games and culture.
Swimming and tennis stars matter when something significant just happened;
a famous name, ordinary interview, college recruitment or routine local meet
alone is not major news. A college coach obituary, merchandise guide, old
movie trivia, industry sales report or adult celebrity gossip is not good Fun.
Do not reward a source just because it is labelled sport or entertainment.

Prefer different real-world events, subjects, topic groups and publishers near
the top. A playful robot belongs here; government AI rules and other civic
technology belong in News, while animal biology research belongs in Science.
Do not return a candidate that JEV has already rejected: this input is a
qualified, same-event-deduplicated catalog. Keep questionable but distinct
items at the end rather than inventing facts or excluding list numbers.

Return ONLY a JSON array of ALL input numbers in best-to-worst order, each
number exactly once. No object, title, reason, markdown, or other text.
Example for four inputs: [3,1,4,2]"""


def _numbered_input(catalog: list[dict]) -> str:
    candidates = []
    for number, brief in enumerate(catalog, 1):
        summary = re.sub(r"<[^>]+>", " ", brief.get("summary") or "")
        candidates.append({"n": number, "title": brief.get("title") or "",
                           "source": brief.get("_source_name") or "",
                           "topic": topic_group(brief),
                           "summary": " ".join(summary.split())[:250]})
    return json.dumps({"candidates": candidates}, ensure_ascii=False)


def _choose_curator(ordered: list[dict]) -> list[dict]:
    """Keep source/topic breadth without admitting known below-floor filler."""
    chosen: list[dict] = []
    seen: set[int] = set()
    for source_cap, topic_cap, floor in (
            (2, 2, FUN_PICK_FLOOR),
            (2, None, FUN_PICK_FLOOR),
            (3, None, FUN_PICK_FLOOR),
            (None, None, FUN_PICK_FLOOR),
            (None, None, None)):
        sources = Counter(b.get("_source_name") or "" for b in chosen)
        topics = Counter(topic_group(b) for b in chosen if topic_group(b))
        for brief in ordered:
            if len(chosen) == FUN_CURATOR_SLOTS:
                return chosen
            if id(brief) in seen:
                continue
            if floor is None and len(chosen) >= MIN_SEND:
                break
            rank = brief.get("_jev_rank") or {}
            if floor is not None and float(rank.get("editorial_pick") or 0) < floor:
                continue
            source = brief.get("_source_name") or ""
            topic = topic_group(brief)
            if source_cap is not None and sources[source] >= source_cap:
                continue
            if topic_cap is not None and topic and topics[topic] >= topic_cap:
                continue
            chosen.append(brief)
            seen.add(id(brief))
            sources[source] += 1
            if topic:
                topics[topic] += 1
    return chosen


def rerank_fun_catalog(catalog: list[dict], *, call: Callable | None = None
                       ) -> tuple[list[dict], dict]:
    """Use a model only when more quality candidates exist than curator slots."""
    count = min(len(catalog), MAX_FUN_COMPARISON)
    report = {"status": "skipped", "compared": count, "sent": 0}
    if count < 2:
        return catalog, report
    qualified = sum(float((b.get("_jev_rank") or {}).get("editorial_pick") or 0)
                    >= FUN_PICK_FLOOR for b in catalog[:count])
    if qualified <= FUN_CURATOR_SLOTS:
        # JEV can already send every qualified option. An extra DeepSeek
        # ranking cannot broaden the shortlist and would cost money on thin
        # Fun days; the existing curator still compares those options.
        report.update(status="skipped_thin_pool", qualified=qualified)
        return catalog, report
    if call is None:
        from .news_rss_core import deepseek_call
        call = deepseek_call
    try:
        answer = call(SYSTEM_PROMPT, _numbered_input(catalog[:count]),
                      max_tokens=512, temperature=0.1, max_attempts=1,
                      json_mode=False)
        if not _valid_permutation(answer, count):
            raise ValueError("response is not a complete numeric permutation")
        ordered = [catalog[n - 1] for n in answer] + catalog[count:]
        chosen = _choose_curator(ordered[:count])
        chosen_ids = {id(b) for b in chosen}
        for pos, brief in enumerate(ordered, 1):
            rank = brief.get("_jev_rank") or {}
            brief["_jev_rank"] = {**rank, "pos": pos,
                                   "send": id(brief) in chosen_ids,
                                   "global_rank": pos if pos <= count else None}
        report.update(status="applied", sent=len(chosen))
        log.info("Fun whole-catalog rank: compared %d, sent %d; top: %s",
                 count, len(chosen), answer[:10])
        return ordered, report
    except Exception as exc:  # optional editorial aid must not block publication
        log.warning("Fun whole-catalog rank ignored (%s); retaining JEV order", exc)
        report["status"] = "ignored"
        return catalog, report
