"""Final seven-day event review, independent of lexical rank shortcuts.

One Choice call compares a candidate with its own section's seven-day history.
An unavailable/uncertain review is not a clean result. The guard is also used
for late spares and checkpoint resumes; results are cached within one run.
"""
from __future__ import annotations

from datetime import date, timedelta
from dataclasses import dataclass
import logging
import math
import re
import time

from .jev_prefilter import make_client

log = logging.getLogger("publication-history")
MIN_CONFIDENCE = .70
MAX_CALLS = 40
MAX_REVIEW_SECONDS = 60
EVENT_RULE = (
    "Compare the actual event, not shared words, topic, outlet or person. "
    "Different wording and another outlet do not make an event new. "
    "Routine impacts/updates of the same ongoing storm, flood, visit or "
    "tournament remain the same event family. Different storms in different "
    "regions and genuinely independent new events are distinct. Do not infer "
    "a major new development unless the candidate states it."
)


@dataclass
class HistoryReviewBudget:
    calls: int = 0
    seconds: float = 0.0


class PublicationHistoryGuard:
    def __init__(self, rows, *, category=None, client=None, budget=None):
        self.category = category
        self.rows = [r for r in rows if category is None or r.get("category") == category]
        self.client = client
        self.budget = budget if budget is not None else HistoryReviewBudget()
        self.cache = {}
        self.calls = self.input_tokens = self.output_tokens = 0
        self.usage_reported_calls = 0
        self.seconds = 0.0
        self.blocked = []

    @classmethod
    def load(cls, today, category, *, budget=None):
        from .supabase_io import client
        start = (date.fromisoformat(today) - timedelta(days=7)).isoformat()
        # Deliberately strict: a failed history query must not look like no history.
        rows = client().table("redesign_stories").select(
            "source_title,source_url,published_date,category"
        ).eq("category", category).gte("published_date", start).lt("published_date", today).eq(
            "archived", False).execute().data
        if rows is None:
            raise RuntimeError("publication history lookup returned no result")
        log.info("publication history [%s]: %d stories [%s, %s)",
                 category, len(rows), start, today)
        return cls(rows, category=category, budget=budget)

    def _usage(self, response):
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.usage_reported_calls += 1
            self.input_tokens += int(getattr(usage, "input_tokens", 0) or 0)
            self.output_tokens += int(getattr(usage, "output_tokens", 0) or 0)

    def review(self, brief):
        from .full_round import _canonical_source_url
        title = (brief.get("title") or "").strip()
        summary = re.sub(r"<[^>]+>", " ", brief.get("summary") or "")[:600]
        url = _canonical_source_url(brief.get("link") or "")
        key = (title, summary, url)
        if key in self.cache:
            return self.cache[key]
        if not self.rows:
            result = {"status": "clear", "method": "empty_history"}
        else:
            exact = next((r for r in self.rows if
                          (url and url == _canonical_source_url(r.get("source_url") or ""))
                          or (title and title.casefold() == (r.get("source_title") or "").casefold())), None)
            if exact:
                result = {"status": "duplicate", "method": "exact", "match": exact}
            else:
                result = self._semantic_review(title, summary)
        self.cache[key] = result
        if result["status"] != "clear":
            self.blocked.append({"title": title, **result})
            log.warning("publication history %s: %s — %s", result["status"],
                        title, result.get("match") or result.get("reason"))
        return result

    def allows(self, brief):
        return self.review(brief)["status"] == "clear"

    def _semantic_review(self, title, summary):
        if not title:
            return {"status": "unverified", "reason": "missing headline"}
        if self.budget.calls >= MAX_CALLS or self.budget.seconds >= MAX_REVIEW_SECONDS:
            return {"status": "unverified", "reason": "history review call budget exhausted"}
        client = self.client
        owned = client is None
        t0 = time.monotonic()
        try:
            if owned:
                client, why = make_client()
                if client is None:
                    raise RuntimeError(why)
            from typesafe_sdk import Choice, Noul
            options = {f"past_{i}": f"{r.get('published_date', '')}: {r.get('source_title', '')}"
                       for i, r in enumerate(self.rows)}
            options["none"] = "No listed event is repeated by this candidate"
            self.calls += 1
            self.budget.calls += 1
            response = client.system_one(
                state={"headline": title, "summary": summary},
                questions={"published_event": Choice(
                    instructions="Choose the previously published event this candidate repeats, or none. " + EVENT_RULE,
                    criteria=options)})
            self._usage(response)
            answer = response.answers["published_event"]
            confidence = float(answer.confidence)
            if answer.choice not in options or not math.isfinite(confidence) or not 0 <= confidence <= 1:
                raise ValueError("invalid history verdict")
            if confidence < MIN_CONFIDENCE:
                # A multi-way Choice can be uncertain even for a genuinely new story.
                # Resolve with a bounded binary existence check; do not lower the
                # threshold solely to make a troublesome sample pass.
                if self.budget.calls < MAX_CALLS:
                    self.calls += 1
                    self.budget.calls += 1
                    confirmation = client.system_one(
                        state={"headline": title, "summary": summary,
                               "previously_published": list(options.values())[:-1]},
                        questions={"repeated_event": Noul(
                            instructions="Does the candidate repeat ANY of the previously published events? " + EVENT_RULE,
                            criteria={"true": "At least one listed event family is repeated",
                                      "false": "All listed events are distinct from this candidate"})})
                    self._usage(confirmation)
                    repeat = float(confirmation.answers["repeated_event"].noul)
                    if not math.isfinite(repeat) or not 0 <= repeat <= 1:
                        raise ValueError("invalid binary history verdict")
                    if repeat <= .10:
                        return {"status": "clear", "method": "jev_binary_history",
                                "repeat_probability": repeat}
                    if repeat >= .90:
                        return {"status": "duplicate", "method": "jev_binary_history",
                                "reason": "repeats an event in the seven-day history",
                                "repeat_probability": repeat}
                return {"status": "unverified", "reason": "uncertain history verdict",
                        "confidence": confidence, "choice": answer.choice}
            if answer.choice == "none":
                return {"status": "clear", "method": "jev_full_history", "confidence": confidence}
            return {"status": "duplicate", "method": "jev_full_history", "confidence": confidence,
                    "match": self.rows[int(answer.choice.removeprefix("past_"))]}
        except Exception as exc:
            return {"status": "unverified", "reason": str(exc)[:160]}
        finally:
            elapsed = time.monotonic() - t0
            self.seconds += elapsed
            self.budget.seconds += elapsed
            if owned and client is not None:
                try:
                    client.close()
                except Exception:
                    pass

    def report(self):
        return {"category": self.category, "history_stories": len(self.rows), "calls": self.calls,
                "usage_reported_calls": self.usage_reported_calls,
                "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "seconds": round(self.seconds, 2), "blocked": self.blocked}


def winner_brief(winner):
    # Preserve the source article URL/summary when a checkpoint's brief is sparse.
    return {**(winner.get("winner") or {}),
            **(winner.get("_brief") or winner.get("_winner_brief") or {})}


def assert_history_clear(stories_by_cat, guard):
    """Run even after a safety checkpoint resume, before emit/persist/upload."""
    blocked = [f"{cat}: {winner_brief(w).get('title', '')}"
               for cat, stories in stories_by_cat.items() for w in stories
               if not guard.allows(winner_brief(w))]
    if blocked:
        raise RuntimeError("Publication history gate blocked: " + " | ".join(blocked))
    # A thin fresh section can continue to packaging after the full catalog
    # and today's deeper feed candidates have been exhausted.
