"""Conservative Jev section routing before the mega curator narrows candidates.

This is not a safety decision. Ambiguous or unavailable judgments keep the
feed's original section; the existing category-fit gate remains downstream.
"""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from .jev_prefilter import WORKERS, make_client
from .editorial_policy import SECTION_POLICY, explicit_section

log = logging.getLogger("editorial-routing")

SECTIONS = ("News", "Science", "Fun")
MIN_MOVE_CONFIDENCE = 0.90
SECTION_CRITERIA = {
    "News": "Current affairs: government, elections, diplomacy, conflict, severe weather, public health, and technology/AI with civic or public-policy consequences",
    "Science": "Physics, chemistry, astronomy, Earth/climate, biology including animal research/species/ecology, medicine and archaeology, or underlying technology research",
    "Fun": "Playful technology and AI such as robots, inventions and games, plus animal happenings/entertainment (not biology or animal research), sports, music, movies, arts, contests, kid achievements and history",
}
SECTION_INSTRUCTIONS = (
    "Choose the best section for a US kids news site. Judge the actual story, "
    "not the feed label. " + SECTION_POLICY + " "
    "Return one best section."
)


def mode() -> str:
    value = (os.environ.get("JEV_ROUTE") or "on").strip().lower()
    return value if value in {"on", "shadow", "off"} else "on"


def route_briefs(briefs_by_cat: dict[str, list[dict]], *, client=None,
                 route_mode: str | None = None) -> tuple[dict[str, list[dict]], dict]:
    """Move only high-confidence misfiled briefs; preserve all others.

    A failed/uncertain Jev call never drops a brief. Shadow mode records the
    proposed section but leaves the current pipeline buckets untouched.
    """
    selected_mode = route_mode or mode()
    report = {"mode": selected_mode, "scored": 0, "uncertain": 0,
              "failed": 0, "moved": []}
    if selected_mode == "off":
        return briefs_by_cat, report
    flat = [(cat, brief) for cat, briefs in briefs_by_cat.items() for brief in briefs]
    if not flat:
        return briefs_by_cat, report
    own_client = client is None
    if own_client:
        client, why = make_client()
        if client is None:
            log.warning("section routing unavailable (%s); keeping feed sections", why)
            report["failed"] = len(flat)
            return briefs_by_cat, report
    try:
        try:
            from typesafe_sdk import Choice
        except ImportError as e:
            log.warning("section routing unavailable (%s); keeping feed sections", e)
            report["failed"] = len(flat)
            return briefs_by_cat, report
        question = {"section": Choice(instructions=SECTION_INSTRUCTIONS,
                                      criteria=SECTION_CRITERIA)}

        def _one(brief: dict):
            answer = client.system_one(
                state={"headline": (brief.get("title") or "")[:240],
                       "summary": (brief.get("summary") or "")[:600]},
                questions=question,
            ).answers["section"]
            return answer.choice, float(answer.confidence)

        judgments: dict[int, tuple[str, float]] = {}
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futures = {ex.submit(_one, brief): (cat, brief) for cat, brief in flat}
            for fut in as_completed(futures):
                cat, brief = futures[fut]
                try:
                    target, confidence = fut.result()
                    if target not in SECTIONS or not 0 <= confidence <= 1:
                        raise ValueError(f"invalid Jev section {target!r}/{confidence}")
                    judgments[id(brief)] = target, confidence
                    report["scored"] += 1
                except Exception as e:  # noqa: BLE001 — fail open per brief
                    report["failed"] += 1
                    log.warning("section routing failed for %s: %s",
                                (brief.get("title") or "")[:60], e)

        out = {cat: [] for cat in briefs_by_cat}
        for cat, brief in flat:
            target, confidence = judgments.get(id(brief), (cat, 0.0))
            forced = explicit_section(brief)
            if forced and forced != cat:
                target, confidence = forced, 1.0
            if target != cat and confidence >= MIN_MOVE_CONFIDENCE and target in out:
                brief["_jev_routed_from"] = cat
                brief["_jev_route_confidence"] = round(confidence, 3)
                brief["_jev_route_target"] = target
                report["moved"].append({"from": cat, "to": target,
                                        "title": brief.get("title") or "",
                                        "confidence": round(confidence, 3)})
                if selected_mode == "on":
                    brief["_category"] = target
                    out[target].append(brief)
                    continue
            elif target != cat:
                report["uncertain"] += 1
            out[cat].append(brief)
        return out, report
    finally:
        if own_client:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass
