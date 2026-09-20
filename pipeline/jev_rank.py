"""Stage 1.7 of the mega pipeline: Jev ranks every probed candidate, so the
curator sees the best 6 per category instead of the first 10 in feed order.

Why: the probe used to keep the first 10 length-valid briefs per category in
source-interleaved order — a blind cut. Over 18 days it discarded 15 of 25
valid Science candidates and 10 of 21 Fun candidates a day without anything
judging them. This stage replaces that cut with a ranking.

    probe pool (uncapped) --rank--> [ top 6 -> curator ] + [ next 4 -> Stage 3 spares ]

Everything downstream is unchanged: the curator still ranks 5, 4 are rewritten,
3 ship, and it still applies its own source / subject / cluster rules.

Jev scores each brief on its own and cannot see its neighbours, so what needs
to see more than one brief is done here, code first:
  · at most 2 of the 6 from one source            code
  · near-identical headlines                      code (mega_curator.titles_same_story)
  · same story told in different words            Jev, asked only about pairs whose
    (within a category and across categories)     headlines share a content word
  · News: at most 3 of the 6 about one person     Jev, same gate. A CAP, not a ban: the
    or organisation                               curator owns "3 different subjects in the
                                                  top 3" and can only obey it if the 6 leave
                                                  it a choice. Which of several Trump stories
                                                  survives stays its call — a story removed
                                                  here is one it can never bring back.

Ranking key is the `pick` noul. On 100 stories labelled blind for this audience
it reached AUC 0.96 against the label; `want` is kept as an annotation.
NOTE: that labeller also wrote AUDIENCE below, so the figure shows that Jev
follows this brief faithfully, not that the brief is right. Edit AUDIENCE to
change what gets picked.

FAIL-OPEN, same contract as jev_prefilter: any trouble returns None and the
caller falls back to the legacy cut (first 10 in feed order).

    JEV_RANK=on      (default) rank and narrow
    JEV_RANK=shadow  rank, log what would have been sent, change nothing
    JEV_RANK=off     skip
"""
from __future__ import annotations

import logging
import math
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .jev_prefilter import MAX_ERROR_RATE, WORKERS, make_client
from .mega_curator import titles_same_story

log = logging.getLogger("jev-rank")

TO_CURATOR = 6              # the curator ranks 5 of these; one is its to drop
MAX_PER_SOURCE = 2          # among the 6, so its "3 different sources in the top 3" rule stays satisfiable
MAX_SAME_SUBJECT = 3        # News only: a cap, not a ban — see _select
POOL_KEEP = 10              # top 6 + 4 reserve spares, in rank order
TIME_BUDGET_S = 90.0
SAME_MIN = 0.50
CROSS_CAT_ORDER = ("Fun", "Science", "News")   # earlier category keeps a shared story

AUDIENCE = {
    "who": "Children aged 10 to 14 living in the United States, reading a daily news site made for them.",
    "they_choose": "Stories they can picture and retell: animals, space, dinosaurs and fossils, records and firsts, "
                   "sport and athletes they follow, games, films and characters made for their age, "
                   "kids doing remarkable things, weird science.",
    "they_skip": "Stories that need adult background: legislative procedure, party finance, sanctions, markets, "
                 "product shopping advice, adult film and art criticism, and the local politics of other countries.",
    "editor_also_runs": "A few major world or US events each day that a child should know about even if they "
                        "would not pick them first.",
}
PICK_Q = "Would the editor put this story in today's edition for the reader described in `audience`?"
PICK_CRITERIA = {
    "true": "The reader would choose it, or it is a major world or US event they should know about",
    "false": "It is for adults, needs adult background, is shopping advice, is local to another country, "
             "or is not a single news story",
}
WANT_Q = "Match this story to the reaction of the reader described in `audience`"
WANT_LEVELS = [
    "The reader would scroll past: it is written for adults about adult concerns",
    "The reader could follow it but has no reason to care",
    "The reader would read it if it were in front of them",
    "The reader would pick it from a list of headlines",
    "The reader would tell a friend about it afterwards",
]
SAME_STORY_Q = "Do these two headlines report on the same real-world event or the same ongoing story?"
SAME_SUBJECT_Q = "Do both stories center on the same single person or the same single organization?"

_STOP = frozenset("the a an and or of to in on for with from at by as is are was were be been it its this that "
                  "after before over into about new says say said will would could has have had not but how why "
                  "what when who than more most their his her they you your our us".split())


def mode() -> str:
    m = (os.environ.get("JEV_RANK") or "on").strip().lower()
    return m if m in {"on", "shadow", "off"} else "on"


def _text(b: dict) -> tuple[str, str]:
    return (b.get("title") or ""), re.sub(r"<[^>]+>", " ", b.get("summary") or "")[:600]


def _tokens(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{4,}", title.lower()) if w not in _STOP}


def _questions():
    from typesafe_sdk import Noul, Score
    return ({"pick": Noul(instructions=PICK_Q, criteria=PICK_CRITERIA),
             "want": Score(instructions=WANT_Q, criteria=WANT_LEVELS)},
            {"same_story": Noul(instructions=SAME_STORY_Q)},
            {"same_story": Noul(instructions=SAME_STORY_Q), "same_subject": Noul(instructions=SAME_SUBJECT_Q)})


def _score_one(client, q, cat: str, b: dict) -> dict:
    title, summary = _text(b)
    ans = client.system_one(
        state={"audience": AUDIENCE,
               "story": {"section": cat, "headline": title, "summary": summary,
                         "outlet": b.get("_source_name") or ""}},
        questions=q).answers
    pick, want = float(ans["pick"].noul), float(ans["want"].score)
    if not (math.isfinite(pick) and 0 <= pick <= 1 and math.isfinite(want) and 0 <= want <= len(WANT_LEVELS) - 1):
        raise ValueError(f"jev returned out-of-range answers: pick={pick} want={want}")
    return {"pick": round(pick, 3), "want": round(want, 2)}


class _Pairs:
    """How two briefs relate: "story", "subject" or None. Code first — Jev is asked
    only when the headlines share a content word yet are not near-identical. A failed
    call answers None: it must never block a pick. Answers are cached per pair."""

    def __init__(self, client, q_story, q_both, deadline: float):
        self.client, self.q_story, self.q_both, self.deadline = client, q_story, q_both, deadline
        self.calls = self.errors = 0
        self._cache: dict[tuple[int, int, bool], str | None] = {}

    def relation(self, a: dict, b: dict, *, subject: bool) -> str | None:
        ta, tb = a.get("title") or "", b.get("title") or ""
        if (a.get("link") and a.get("link") == b.get("link")) or titles_same_story(ta, tb):
            return "story"
        if not (_tokens(ta) & _tokens(tb)) or time.monotonic() > self.deadline:
            return None
        key = (min(id(a), id(b)), max(id(a), id(b)), subject)
        if key not in self._cache:
            self._cache[key] = self._ask(a, b, subject)
        return self._cache[key]

    def _ask(self, a: dict, b: dict, subject: bool) -> str | None:
        self.calls += 1
        try:
            (ha, sa), (hb, sb) = _text(a), _text(b)
            ans = self.client.system_one(
                state={"headline_A": ha, "summary_A": sa[:300], "headline_B": hb, "summary_B": sb[:300]},
                questions=self.q_both if subject else self.q_story).answers
            if float(ans["same_story"].noul) > SAME_MIN:
                return "story"
            if subject and float(ans["same_subject"].noul) > SAME_MIN:
                return "subject"
        except Exception as e:  # noqa: BLE001
            self.errors += 1
            log.warning("  jev pair call failed: %s", e)
        return None


def _select(cat: str, ranked: list[dict], taken_elsewhere: list[dict], pairs: _Pairs) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Greedy top-TO_CURATOR under the cross-brief rules. Returns (chosen, skipped)."""
    news = cat == "News"
    chosen: list[dict] = []
    skipped: list[tuple[dict, str]] = []
    for b in ranked:
        if len(chosen) == TO_CURATOR:
            break
        why = None
        if sum(c.get("_source_name") == b.get("_source_name") for c in chosen) >= MAX_PER_SOURCE:
            why = f"already {MAX_PER_SOURCE} from this source"
        else:
            rel = [pairs.relation(c, b, subject=news) for c in chosen]
            if "story" in rel:
                why = "same story as a higher-ranked pick"
            elif rel.count("subject") >= MAX_SAME_SUBJECT:
                why = f"already {MAX_SAME_SUBJECT} about the same subject"
            else:
                other = next((c for c in taken_elsewhere if pairs.relation(c, b, subject=False) == "story"), None)
                if other is not None:
                    why = f"same story as a {other.get('_category') or 'other'} pick"
        if why:
            skipped.append((b, why))
        else:
            chosen.append(b)
    # A thin pool must still fill the curator's slots: relax the caps, never same-story.
    for b, why in list(skipped):
        if len(chosen) == TO_CURATOR:
            break
        if "same story" not in why:
            chosen.append(b)
            skipped.remove((b, why))
    return chosen, skipped


def for_curator(pool: dict[str, list[dict]]) -> dict[str, list[dict]]:
    return {cat: [b for b in bs if (b.get("_jev_rank") or {}).get("send")] for cat, bs in pool.items()}


def rank_briefs(briefs_by_cat: dict[str, list[dict]], *, client=None) -> tuple[dict[str, list[dict]] | None, dict]:
    """Returns ({cat: briefs in rank order, at most POOL_KEEP}, report), or (None, report)
    when the ranking cannot be trusted. Briefs flagged `_jev_rank["send"]` go to the
    curator (use `for_curator`, never a positional slice: a thin pool sends fewer than
    TO_CURATOR); the rest are Stage 3 spares in rank order. Never raises, never mutates
    the input lists (briefs gain a `_jev_rank` annotation)."""
    report: dict = {"jev": "skipped", "pair_calls": 0, "skipped": [], "sent": {}}
    t0 = time.monotonic()
    own_client = client is None
    try:
        if client is None:
            client, why = make_client()
            if client is None:
                report["jev"] = f"IGNORED ({why})"
                return None, report
        q_rank, q_story, q_both = _questions()
        flat = [(cat, b) for cat, briefs in briefs_by_cat.items() for b in briefs]
        if not flat:
            report["jev"] = "IGNORED (no briefs)"
            return None, report

        scores: dict[int, dict] = {}
        errors = 0
        ex = ThreadPoolExecutor(max_workers=WORKERS)
        try:
            futs = {ex.submit(_score_one, client, q_rank, cat, b): b for cat, b in flat}
            try:
                for fut in as_completed(futs, timeout=TIME_BUDGET_S):
                    try:
                        scores[id(futs[fut])] = fut.result()
                    except Exception as e:  # noqa: BLE001
                        errors += 1
                        log.warning("  jev rank call failed (%s): %s", (futs[fut].get("title") or "")[:60], e)
            except TimeoutError:
                report["jev"] = f"IGNORED (time budget {TIME_BUDGET_S:.0f}s exceeded)"
                return None, report
        finally:
            ex.shutdown(wait=False, cancel_futures=True)
        if errors / len(flat) > MAX_ERROR_RATE:
            report["jev"] = f"IGNORED ({errors}/{len(flat)} calls failed)"
            return None, report

        pairs = _Pairs(client, q_story, q_both, deadline=t0 + TIME_BUDGET_S)
        out: dict[str, list[dict]] = {}
        taken: list[dict] = []
        order = [c for c in CROSS_CAT_ORDER if c in briefs_by_cat] + [c for c in briefs_by_cat if c not in CROSS_CAT_ORDER]
        for cat in order:
            # An unscored brief (its call failed) ranks last rather than being lost.
            ranked = sorted(briefs_by_cat[cat], key=lambda b: -(scores.get(id(b)) or {"pick": -1})["pick"])
            chosen, skipped = _select(cat, ranked, taken, pairs)
            taken += chosen
            # Reserve order: unchosen by rank, with same-story duplicates last — a
            # duplicate must never reach the curator by filling a thin pool's slots.
            dup_ids = {id(b) for b, why in skipped if "same story" in why}
            rest = [b for b in ranked if not any(b is c for c in chosen)]
            rest = [b for b in rest if id(b) not in dup_ids] + [b for b in rest if id(b) in dup_ids]
            final = (chosen + rest)[:max(POOL_KEEP, len(chosen))]
            for pos, b in enumerate(final, start=1):
                b["_jev_rank"] = {**(scores.get(id(b)) or {}), "pos": pos, "send": pos <= len(chosen)}
            out[cat] = final
            report["sent"][cat] = [{"pos": i, "pick": (scores.get(id(b)) or {}).get("pick"),
                                    "source": b.get("_source_name"), "title": b.get("title")}
                                   for i, b in enumerate(chosen, start=1)]
            report["skipped"] += [{"cat": cat, "title": b.get("title"), "why": why} for b, why in skipped]
        out = {cat: out[cat] for cat in briefs_by_cat}          # caller's category order
        report["pair_calls"] = pairs.calls
        report["jev"] = (f"{len(flat) - errors}/{len(flat)} scored, {pairs.calls} pair checks"
                         f"{f' ({pairs.errors} failed)' if pairs.errors else ''} in {time.monotonic() - t0:.1f}s")
        return out, report
    except Exception as e:  # noqa: BLE001 — belt and braces: never break the run
        report["jev"] = f"IGNORED (unexpected error: {e})"
        return None, report
    finally:
        if own_client and client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass
