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
  · a floor on `pick`, per category               code (FLOOR) — below it a brief is
                                                  only sent to fill up to MIN_SEND
  · at most 2 of the 6 from one source            code, unless the 3rd beats the
                                                  alternative by CAP_YIELD_GAP and
                                                  MIN_DISTINCT_SOURCES still holds
  · near-identical headlines                      code (mega_curator.titles_same_story)
  · same story told in different words            Jev, asked only about pairs whose
    (within the same category)                   headlines share a content word
  · already published in the last 7 days,          code, then Jev ("same single event?")
    in the same category                          — the legacy filter only compares inside
                                                  one category at 80% title similarity
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
from .mega_curator import briefs_same_event, join_event_group, titles_same_story
from .editorial_policy import publisher_key, editorial_exclusion, SCIENCE_MIN_PUBLISHERS
from .editorial_policy import low_fun_value, important_news
from .editorial_policy import SECTION_POLICY

log = logging.getLogger("jev-rank")

TO_CURATOR = 6              # the curator ranks 5 of these; one is its to drop
TO_CURATOR_BY_CATEGORY = {"News": 6, "Science": 6, "Fun": 7}
MIN_SEND = 4                # below this the floor yields — see FLOOR
MAX_PER_SOURCE = 2          # within the shortlist; Science groups by publisher, others by feed
MIN_DISTINCT_SOURCES = 3    # what the curator's top-3 rule needs to be satisfiable at all
CAP_YIELD_GAP = 0.10        # a 3rd from one source beats an alternative this much worse
HARD_PER_SOURCE = 3         # the cap may be exceeded by one brief, never more
MAX_SAME_SUBJECT = 3        # News only: a cap, not a ban — see _select
POOL_KEEP = 10              # up to 6/6/7 sent; remaining entries are reserve spares
CATEGORY_FIT_MIN = 0.60     # wrong-section stories never reach curator/spares
DEEP_DIG_BORDERLINE_MAX = 0.70  # only uncertain late backfill pays for cross-section checks
DEEP_DIG_FIT_MARGIN = 0.05     # target must beat the best alternative, not merely pass 0.60

# Minimum `pick` to be sent to the curator without comment. Calibrated on 100
# stories labelled blind for this audience (jev-probes/data/gold_labels.py):
# News scores far lower than the rest because the audience brief says kids skip
# adult topics and News IS adult topics — a single global floor at 0.6 keeps 16
# of 30 Science candidates and ZERO News ones. These are per-category for that
# reason, not because News deserves a lower bar.
#   News    good stories median 0.50, 0.40 keeps 9/40 at 67% precision
#   Science good stories median 0.74, 0.50 keeps 20/30 at 95% precision
#   Fun     good stories median 0.70, 0.50 keeps  8/30 at 62% precision
# The floor is a preference, not a gate: if fewer than MIN_SEND clear it, the
# best below-floor candidates fill up to MIN_SEND and are logged as such. A
# thin day should publish a weak story, not go blank — but it should say so.
FLOOR = {"News": 0.40, "Science": 0.50, "Fun": 0.50}
DEFAULT_FLOOR = 0.45
TIME_BUDGET_S = 90.0
SAME_MIN = 0.50
CROSS_CAT_ORDER = ("Fun", "Science", "News")   # processing order only; section pools are independent

AUDIENCE = {
    "who": "Children aged 10 to 14 living in the United States, reading a daily news site made for them.",
    "they_choose": "Stories they can picture and retell: animals, space, dinosaurs and fossils, records and firsts, "
                   "major swimming and tennis results and athletes they follow, games, films and characters made for their age, "
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
SPORTS_PRIORITY_Q = (
    "For a CURRENT Fun story, how significant is its NEW swimming or tennis development "
    "to young fans? Score the actual new event, not just a famous name, an old match "
    "recounted in a fresh interview, or a headline using the word 'record'. "
    "Other sports and non-sports score 0."
)
SPORTS_PRIORITY_LEVELS = [
    "Not a new swimming or tennis development",
    "Routine swim or tennis item, recruitment, training, profile or old-event recap",
    "Timely swim or tennis result or concrete update about a notable athlete",
    "Major international meet or Grand Slam key round, national record, or major new star achievement",
    "World record broken, Olympic/World Championship title, Grand Slam champion/final result, or comparable landmark",
]
SPORTS_PRIORITY_BONUS = {3: 0.10, 4: 0.18}  # modest, soft Fun ranking preference
SECTION_VALUE_LEVELS = {
    "News": [
        "Routine adult/local detail with no clear consequence for US children",
        "Limited consequence; being American or mentioning a president alone does not make it important",
        "Useful current affairs context for US children, but not a major development",
        "Significant NEW consequence for US children/families or US public life: schools, health, environment, rights, civic life",
        "Major NEW national or world development with substantial consequences for the US or US children",
    ],
    "Science": [
        "No clear science learning or discovery value",
        "Routine technical or promotional item with little understandable learning",
        "A clear fact or explanation children can understand",
        "A meaningful new discovery or compelling explanation with a concrete takeaway",
        "A major well-supported discovery or exceptional scientific insight children can understand",
    ],
    "Fun": [
        "No child-facing enjoyment: recruiting, roster paperwork, adult industry or commercial news",
        "Sports/entertainment label only; routine commitments, rankings of recruits or adult business detail",
        "An accessible entertaining technology/AI, animal-happening or cultural story a child might enjoy",
        "A genuinely engaging technology/AI advance, amusing animal event, new sporting result, playful idea or creative achievement",
        "A delightful or remarkable event children would eagerly share; a landmark result for young fans",
    ],
}
SECTION_VALUE_BONUS = {3: .10, 4: .18}


def _section_questions(base, cat):
    from typesafe_sdk import Score
    questions = {**base, "section_value": Score(
        instructions="Evaluate the actual new development for this section and US children aged 10–14. "
                     "Use evidence in the title/summary, not sensational wording or famous names. "
                     "For News use consequences, never political party, ideology or approval of a policy.",
        criteria=SECTION_VALUE_LEVELS.get(cat, SECTION_VALUE_LEVELS["News"]))}
    if cat == "Fun":
        questions["sports_priority"] = Score(instructions=SPORTS_PRIORITY_Q, criteria=SPORTS_PRIORITY_LEVELS)
    return questions
CATEGORY_FIT_Q = "Does this story belong in the named section?"
CATEGORY_FIT_CRITERIA = {
    "true": "The story belongs in the named section under this policy: " + SECTION_POLICY,
    "false": "The story belongs in another section under this policy: " + SECTION_POLICY,
}
SAME_STORY_Q = "Do these headlines cover the same real-world event family or stages/angles of one ongoing event " \
               "that a daily editor should combine into one article?"
# Against already-published stories the question is narrower on purpose: a follow-up
# with a new development ("...admits mistakes") is news; the same event reworded by
# another outlet ("reporters denied access" / "journalists denied access") is not.
SAME_EVENT_Q = "Do these two headlines report the same single event?"
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
             "want": Score(instructions=WANT_Q, criteria=WANT_LEVELS),
             "category_fit": Noul(instructions=CATEGORY_FIT_Q,
                                  criteria=CATEGORY_FIT_CRITERIA)},
            {"same_story": Noul(instructions=SAME_STORY_Q)},
            {"same_story": Noul(instructions=SAME_STORY_Q), "same_subject": Noul(instructions=SAME_SUBJECT_Q)},
            {"same_event": Noul(instructions=SAME_EVENT_Q)})


def _score_one(client, q, cat: str, b: dict) -> dict:
    title, summary = _text(b)
    ans = client.system_one(
        state={"audience": AUDIENCE,
               "story": {"section": cat, "headline": title, "summary": summary,
                         "outlet": b.get("_source_name") or ""}},
        questions=q).answers
    pick, want = float(ans["pick"].noul), float(ans["want"].score)
    category_fit = float(ans["category_fit"].noul)
    sports_priority = float(getattr(ans.get("sports_priority"), "score", 0) or 0)
    value = float(ans["section_value"].score) if "section_value" in q else None
    if not (math.isfinite(pick) and 0 <= pick <= 1
            and math.isfinite(want) and 0 <= want <= len(WANT_LEVELS) - 1
            and math.isfinite(category_fit) and 0 <= category_fit <= 1
            and math.isfinite(sports_priority) and 0 <= sports_priority <= 4
            and (value is None or math.isfinite(value) and 0 <= value <= 4)):
        raise ValueError(
            f"jev returned out-of-range answers: pick={pick} want={want} "
            f"category_fit={category_fit} sports_priority={sports_priority}"
        )
    priority_band = min(4, max(0, int(sports_priority + 0.5)))
    bonus = SPORTS_PRIORITY_BONUS.get(priority_band, 0) if cat == "Fun" else 0
    # Do not stack two bonuses for the same sporting achievement.
    bonus = max(bonus, SECTION_VALUE_BONUS.get(int(value), 0) if value is not None else 0)
    return {"pick": round(pick, 3), "want": round(want, 2),
            **({"section_value": round(value, 2)} if value is not None else {}),
            "category_fit": round(category_fit, 3),
            "sports_priority": round(sports_priority, 2) if cat == "Fun" else 0,
            "editorial_pick": round(min(1.0, pick + bonus), 3)}


def gate_deep_dig_category(cat: str, briefs: list[dict], client=None) -> list[dict]:
    """Score late RSS backfill before it can bypass the normal category gate.

    Unlike the first-round Jev ranking, deep-dig is optional: if scoring is
    unavailable or a call fails, keep the existing published story instead of
    promoting an unclassified article into the wrong section.
    """
    if not briefs:
        return []
    own_client = client is None
    if own_client:
        client, why = make_client()
        if client is None:
            log.warning("  [%s] deep-dig category gate unavailable (%s); skipping %d briefs",
                        cat, why, len(briefs))
            return []
    try:
        q_base = _questions()[0]
        q_rank = _section_questions(q_base, cat)
        accepted: set[int] = set()
        borderline: list[dict] = []
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(_score_one, client, q_rank, cat, b): b for b in briefs}
            for fut in as_completed(futs):
                b = futs[fut]
                try:
                    score = fut.result()
                    fit = score["category_fit"]
                    b["_jev_rank"] = {**score, "floor": FLOOR.get(cat, DEFAULT_FLOOR)}
                    if cat == "Fun" and low_fun_value(b):
                        continue
                except Exception as e:  # noqa: BLE001 — unscored backfill is not safe to promote
                    log.warning("  [%s] deep-dig category score failed for %s: %s",
                                cat, (b.get("title") or "")[:60], e)
                    continue
                b["_jev_category_fit"] = fit
                if fit >= DEEP_DIG_BORDERLINE_MAX:
                    accepted.add(id(b))
                elif fit >= CATEGORY_FIT_MIN:
                    borderline.append(b)
        # A single-section score of 0.60-0.69 can be a false positive: in the
        # 2026-09-26 audit, a hurricane scored 0.61 for Science but 0.84 for
        # News. Ask Jev about the two alternatives only in this grey zone.
        if borderline:
            alternatives = [other for other in ("News", "Science", "Fun") if other != cat]
            other_scores: dict[int, dict[str, float]] = {id(b): {} for b in borderline}
            with ThreadPoolExecutor(max_workers=WORKERS) as ex:
                futs = {ex.submit(_score_one, client, q_base, other, b): (b, other)
                        for b in borderline for other in alternatives}
                for fut in as_completed(futs):
                    b, other = futs[fut]
                    try:
                        other_scores[id(b)][other] = fut.result()["category_fit"]
                    except Exception as e:  # noqa: BLE001 — uncertain backfill fails closed
                        log.warning("  [%s] deep-dig cross-section score failed for %s: %s",
                                    cat, (b.get("title") or "")[:60], e)
            for b in borderline:
                scores = other_scores[id(b)]
                b["_jev_other_category_fit"] = scores
                if (len(scores) == len(alternatives)
                        and b["_jev_category_fit"] >= max(scores.values()) + DEEP_DIG_FIT_MARGIN):
                    accepted.add(id(b))
                else:
                    log.info("  [%s] deep-dig borderline fit %.2f not clearly ahead of %s: %s",
                             cat, b["_jev_category_fit"], scores,
                             (b.get("title") or "")[:60])
        log.info("  [%s] deep-dig category gate: %d/%d fit", cat, len(accepted), len(briefs))
        return [b for b in briefs if id(b) in accepted]
    except Exception as e:  # noqa: BLE001 — optional backfill must not break publication
        log.warning("  [%s] deep-dig category gate failed (%s); skipping backfill", cat, e)
        return []
    finally:
        if own_client:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass


class _Pairs:
    """How two briefs relate: "story", "subject" or None. Code first — Jev is asked
    only when the headlines share a content word yet are not near-identical. A failed
    call answers None: it must never block a pick. Answers are cached per pair."""

    def __init__(self, client, q_story, q_both, q_event, deadline: float):
        self.client, self.q_story, self.q_both, self.q_event, self.deadline = client, q_story, q_both, q_event, deadline
        self.calls = self.errors = 0
        self.published_calls = self.published_input_tokens = self.published_output_tokens = 0
        self._cache: dict[tuple[int, int, bool], str | None] = {}
        self._published: dict[int, str | None] = {}

    def already_published(self, b: dict, recent_titles: list[str]) -> str | None:
        """The published headline this brief repeats, or None. The early
        80%-title-similarity filter catches near-identical titles across
        categories; this Jev pass catches an event another outlet reworded.

        Cached per brief: _select asks up to three times per brief (main pass, then
        each thin-pool fill), and without the cache every ask re-scanned the whole
        recent list and re-sent the Jev calls it had already paid for."""
        if id(b) in self._published:
            return self._published[id(b)]
        self._published[id(b)] = None                # provisional; overwritten on a hit
        title = b.get("title") or ""
        toks = _tokens(title)
        for past in recent_titles:
            if titles_same_story(title, past):
                self._published[id(b)] = past
                return past
            if not (toks & _tokens(past)) or time.monotonic() > self.deadline:
                continue  # cheap early check; final publication review has no lexical gate
            self.calls += 1
            self.published_calls += 1
            try:
                response = self.client.system_one(state={"headline_A": past, "headline_B": title,
                                                         "summary_B": _text(b)[1][:300]},
                                                  questions=self.q_event)
                usage = getattr(response, "usage", None)
                if usage is not None:
                    self.published_input_tokens += int(getattr(usage, "input_tokens", 0) or 0)
                    self.published_output_tokens += int(getattr(usage, "output_tokens", 0) or 0)
                ans = response.answers
                if float(ans["same_event"].noul) > SAME_MIN:
                    self._published[id(b)] = past
                    return past
            except Exception as e:  # noqa: BLE001
                self.errors += 1
                log.warning("  jev pair call failed: %s", e)
                self.forget_published(b)
        return None

    def forget_published(self, b: dict) -> None:
        """Drop the cached answer for a brief whose call failed, so a retry is
        still possible within the deadline."""
        self._published.pop(id(b), None)

    def relation(self, a: dict, b: dict, *, subject: bool) -> str | None:
        ta, tb = a.get("title") or "", b.get("title") or ""
        if ((a.get("link") and a.get("link") == b.get("link"))
                or briefs_same_event(a, b)):
            join_event_group(a, b)
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
                join_event_group(a, b)
                return "story"
            if subject and float(ans["same_subject"].noul) > SAME_MIN:
                return "subject"
        except Exception as e:  # noqa: BLE001
            self.errors += 1
            log.warning("  jev pair call failed: %s", e)
        return None


def _select(cat: str, ranked: list[dict], pairs: _Pairs,
            recent_titles: list[str]) -> tuple[list[dict], list[tuple[dict, str]], int]:
    """Greedy top-TO_CURATOR. Returns (chosen, skipped, n_sent_below_floor).

    Hard rules never yield: already published, same story as something already
    chosen in this category.

    Soft rules yield when the pool is thin, in this order:
      · the per-source and per-subject caps fill up to TO_CURATOR — those briefs
        are good, they are only over-represented
      · below-floor briefs fill only up to MIN_SEND, and say so in the log — a
        thin day should publish a weak story rather than go blank, but never pad
        a healthy day with one"""
    news = cat == "News"
    to_curator = TO_CURATOR_BY_CATEGORY.get(cat, TO_CURATOR)
    if news:
        ranked = sorted(ranked, key=lambda b: not important_news(b))
    floor = FLOOR.get(cat, DEFAULT_FLOOR)
    pick = lambda b: (b.get("_jev_pick") or 0.0)
    # Multiple ScienceDaily feeds must not each get a separate source quota.
    source_group = lambda b: (publisher_key(b.get("_source")) or b.get("_source_name")) \
        if cat == "Science" else b.get("_source_name")
    distinct = lambda bs: len({source_group(b) for b in bs})
    diversity_target = SCIENCE_MIN_PUBLISHERS if cat == "Science" else MIN_DISTINCT_SOURCES
    group_label = "publisher" if cat == "Science" else "source"

    chosen: list[dict] = []
    hard: list[tuple[dict, str]] = []
    capped: list[tuple[dict, str]] = []
    low: list[tuple[dict, str]] = []

    def hard_reason(b: dict) -> str | None:
        excluded = editorial_exclusion(b)
        if excluded:
            return excluded
        if cat == "Fun" and low_fun_value(b):
            return "low Fun value"
        fit = float(b.get("_jev_category_fit", 1.0))
        if fit < CATEGORY_FIT_MIN:
            return f"category fit {fit:.2f} is below {CATEGORY_FIT_MIN:.2f}"
        past = pairs.already_published(b, recent_titles) if recent_titles else None
        if past:
            return f"same story as published: {past[:60]}"
        if any(pairs.relation(c, b, subject=False) == "story" for c in chosen):
            return "same story as a higher-ranked pick"
        return None

    def cap_may_yield(b: dict, rest: list[dict]) -> bool:
        """True when a 3rd brief from one source is worth more than what replacing it
        would cost. `rest` is what is still eligible below b in the ranking."""
        others = [o for o in rest if source_group(o) != source_group(b)
                  and pick(o) >= floor]
        if others and pick(b) - pick(others[0]) <= CAP_YIELD_GAP:
            return False                                   # a comparable alternative exists
        # Taking b costs a slot; can the set still reach MIN_DISTINCT_SOURCES?
        new_srcs = {source_group(o) for o in others} - {source_group(c) for c in chosen}
        slots_after = to_curator - len(chosen) - 1
        return distinct(chosen) + min(slots_after, len(new_srcs)) >= diversity_target

    for i, b in enumerate(ranked):
        if len(chosen) == to_curator:
            break
        why = hard_reason(b)
        if why:
            hard.append((b, why))
        elif pick(b) < floor:
            low.append((b, f"below the {cat} floor of {floor:.2f}"))
        elif (sum(source_group(c) == source_group(b) for c in chosen) >= MAX_PER_SOURCE
              and (sum(source_group(c) == source_group(b) for c in chosen) >= HARD_PER_SOURCE
                   or not cap_may_yield(b, ranked[i + 1:]))):
            capped.append((b, f"already {MAX_PER_SOURCE} from this {group_label}"))
        elif news and sum(pairs.relation(c, b, subject=True) == "subject" for c in chosen) >= MAX_SAME_SUBJECT:
            capped.append((b, f"already {MAX_SAME_SUBJECT} about the same subject"))
        else:
            if sum(source_group(c) == source_group(b) for c in chosen) >= MAX_PER_SOURCE:
                log.info("  [%s] source cap yielded for %.2f: no comparable alternative left", cat, pick(b))
            chosen.append(b)

    def _fill(pool: list[tuple[dict, str]], limit: int, *, honour_ceiling: bool,
              note=None) -> int:
        """Promote deferred briefs until `limit`. A brief that now hits a HARD rule
        (chosen has grown since the main pass) moves to `hard` with the real reason
        instead of keeping its stale soft one — the run log is the only record of
        why a brief did not ship."""
        n = 0
        for b, why in list(pool):
            if len(chosen) >= limit:
                break
            if honour_ceiling and sum(
                    source_group(c) == source_group(b) for c in chosen) >= HARD_PER_SOURCE:
                continue
            blocked = hard_reason(b)
            if blocked:
                pool.remove((b, why))
                hard.append((b, blocked))
                continue
            chosen.append(b)
            pool.remove((b, why))
            n += 1
            if note:
                note(b)
        return n

    _fill(capped, to_curator, honour_ceiling=True)         # over-represented but good
    _fill(capped, MIN_SEND, honour_ceiling=False,          # a one-source day still needs MIN_SEND
          note=lambda b: log.info("  [%s] over the per-source ceiling to reach %d briefs — thin pool",
                                  cat, MIN_SEND))
    low.sort(key=lambda t: -pick(t[0]))                    # weak: only to keep the day alive
    below = _fill(low, MIN_SEND, honour_ceiling=False,
                  note=lambda b: log.warning(
                      "  [%s] sending %.2f, BELOW the floor of %.2f — thin pool: %s",
                      cat, pick(b), floor, (b.get("title") or "")[:60]))
    return chosen, hard + capped + low, below


def for_curator(pool: dict[str, list[dict]]) -> dict[str, list[dict]]:
    return {cat: [b for b in bs if (b.get("_jev_rank") or {}).get("send")] for cat, bs in pool.items()}


def rank_briefs(briefs_by_cat: dict[str, list[dict]], *, client=None,
                recent_titles: dict[str, list[str]] | None = None) -> tuple[dict[str, list[dict]] | None, dict]:
    """Returns ({cat: briefs in rank order, at most POOL_KEEP}, report), or (None, report)
    when the ranking cannot be trusted. Briefs flagged `_jev_rank["send"]` go to the
    curator (use `for_curator`, never a positional slice: a thin pool sends fewer than
    TO_CURATOR); the rest are Stage 3 spares in rank order. Never raises, never mutates
    the input lists (briefs gain a `_jev_rank` annotation)."""
    report: dict = {"jev": "skipped", "pair_calls": 0, "past_event_calls": 0,
                    "past_event_input_tokens": 0, "past_event_output_tokens": 0,
                    "skipped": [], "sent": {}, "below_floor": {}}
    t0 = time.monotonic()
    own_client = client is None
    try:
        if client is None:
            client, why = make_client()
            if client is None:
                report["jev"] = f"IGNORED ({why})"
                return None, report
        q_rank, q_story, q_both, q_event = _questions()
        questions_by_cat = {cat: _section_questions(q_rank, cat) for cat in briefs_by_cat}
        flat = [(cat, b) for cat, briefs in briefs_by_cat.items() for b in briefs]
        if not flat:
            report["jev"] = "IGNORED (no briefs)"
            return None, report

        scores: dict[int, dict] = {}
        errors = 0
        ex = ThreadPoolExecutor(max_workers=WORKERS)
        try:
            futs = {ex.submit(_score_one, client, questions_by_cat[cat], cat, b): b
                    for cat, b in flat}
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

        pairs = _Pairs(client, q_story, q_both, q_event, deadline=t0 + TIME_BUDGET_S)
        out: dict[str, list[dict]] = {}
        order = [c for c in CROSS_CAT_ORDER if c in briefs_by_cat] + [c for c in briefs_by_cat if c not in CROSS_CAT_ORDER]
        for cat in order:
            # An unscored brief (its call failed) ranks last rather than being lost.
            for b in briefs_by_cat[cat]:
                b["_jev_pick"] = (scores.get(id(b)) or {}).get("editorial_pick", -1.0)
                b["_jev_category_fit"] = (scores.get(id(b)) or {}).get(
                    "category_fit", 1.0)
                b["_jev_rank"] = {**(scores.get(id(b)) or {}), "floor": FLOOR.get(cat, DEFAULT_FLOOR)}
            ranked = sorted(briefs_by_cat[cat], key=lambda b: -b["_jev_pick"])
            chosen, skipped, below = _select(cat, ranked, pairs, (recent_titles or {}).get(cat, []))
            report["below_floor"][cat] = below
            # Reserve order: unchosen by rank, with same-story duplicates last — a
            # duplicate must never reach the curator by filling a thin pool's slots.
            dup_ids = {id(b) for b, why in skipped if "same story" in why}
            rest = [b for b in ranked if not any(b is c for c in chosen)
                    and not editorial_exclusion(b) and not (cat == "Fun" and low_fun_value(b))
                    and not pairs._published.get(id(b))]
            rest = [b for b in rest if id(b) not in dup_ids] + [b for b in rest if id(b) in dup_ids]
            final = (chosen + rest)[:max(POOL_KEEP, len(chosen))]
            for pos, b in enumerate(final, start=1):
                b["_jev_rank"] = {**(scores.get(id(b)) or {}), "pos": pos, "send": pos <= len(chosen),
                                  "floor": FLOOR.get(cat, DEFAULT_FLOOR)}
            out[cat] = final
            report["sent"][cat] = [{"pos": i, "pick": (scores.get(id(b)) or {}).get("editorial_pick"),
                                    "raw_pick": (scores.get(id(b)) or {}).get("pick"),
                                    "sports_priority": (scores.get(id(b)) or {}).get("sports_priority"),
                                    "section_value": (scores.get(id(b)) or {}).get("section_value"),
                                    "source": b.get("_source_name"), "title": b.get("title")}
                                   for i, b in enumerate(chosen, start=1)]
            report["skipped"] += [{"cat": cat, "title": b.get("title"), "why": why} for b, why in skipped]
        out = {cat: out[cat] for cat in briefs_by_cat}          # caller's category order
        report["pair_calls"] = pairs.calls
        report["past_event_calls"] = pairs.published_calls
        report["past_event_input_tokens"] = pairs.published_input_tokens
        report["past_event_output_tokens"] = pairs.published_output_tokens
        report["jev"] = (f"{len(flat) - errors}/{len(flat)} scored, {pairs.calls} pair checks"
                         f"{f' ({pairs.errors} failed)' if pairs.errors else ''} in {time.monotonic() - t0:.1f}s")
        return out, report
    except Exception as e:  # noqa: BLE001 — belt and braces: never break the run
        report["jev"] = f"IGNORED (unexpected error: {e})"
        return None, report
    finally:
        # _jev_pick is scratch state for _select. On any exit — success, refusal or
        # an exception mid-selection — it must not survive onto briefs the caller
        # goes on to checkpoint.
        for bs in briefs_by_cat.values():
            for b in bs:
                b.pop("_jev_pick", None)
        if own_client and client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass
