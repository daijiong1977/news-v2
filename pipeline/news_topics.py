"""Optional Jev editorial-topic labels for News diversity (not event or safety vetting)."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from .jev_prefilter import WORKERS, make_client

log = logging.getLogger("news-topics")

TOPIC_CRITERIA = {
    "us_politics": "US domestic government, elections, courts, policy or White House press access",
    "international_relations": "Diplomacy, summits, treaties, trade talks or relations across countries",
    "war_security": "Armed conflict, military incidents, national security or peace negotiations",
    "severe_weather": "Storms, hurricanes, typhoons, flooding or other acute weather disasters",
    "transport_infrastructure": "Air travel, airports, roads, utilities or public-system disruptions",
    "public_health": "Disease outbreaks, vaccination or community health",
    "science_environment": "Science, astronomy, research, climate or environment without an acute storm",
    "community": "Local human-interest, civic action or community projects",
    "technology_business": "Technology companies, AI business, regulation or corporate disputes",
    "sports": "Sports competitions, athletes or sports governance",
    "entertainment": "Music, television, movies or celebrity culture",
    "other": "None of the above",
}
MIN_CONFIDENCE = 0.70


def topic_group(brief: dict) -> str:
    """Only confident known labels participate in the soft diversity preference."""
    label = brief.get("_jev_topic_group") or ""
    # "other" is a catch-all, not a coherent topic. Never treat two unrelated
    # miscellaneous stories as a duplicate editorial group.
    return label if label in TOPIC_CRITERIA and label != "other" else ""


def tag_news_topics(briefs: list[dict], client=None) -> dict:
    """Tag News briefs with Jev Choice; errors/uncertainty leave the brief ungrouped.

    This never rejects an article. Same-event dedup and the independent final
    full-text child-safety review remain separate, stronger gates.
    """
    report = {"tagged": 0, "uncertain": 0, "failed": 0}
    if not briefs:
        return report
    own_client = client is None
    if own_client:
        client, why = make_client()
        if client is None:
            log.warning("News topic labels unavailable (%s); keeping original order", why)
            report["failed"] = len(briefs)
            return report
    try:
        try:
            from typesafe_sdk import Choice
        except ImportError as e:
            log.warning("News topic labels unavailable (%s); keeping original order", e)
            report["failed"] = len(briefs)
            return report

        question = {"topic": Choice(
            instructions="Choose the PRIMARY editorial topic of this news brief. Different events on the same broad topic share a label; this is not a same-event judgment. US domestic policy/elections/courts are us_politics; international summits are international_relations; storms and flooding are severe_weather. Choose exactly one label.",
            criteria=TOPIC_CRITERIA,
        )}

        def _one(brief: dict):
            ans = client.system_one(
                state={"headline": (brief.get("title") or "")[:240],
                       "summary": (brief.get("summary") or "")[:600]},
                questions=question,
            ).answers["topic"]
            return ans.choice, float(ans.confidence)

        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futures = {ex.submit(_one, brief): brief for brief in briefs}
            for fut in as_completed(futures):
                brief = futures[fut]
                try:
                    label, confidence = fut.result()
                    if label in TOPIC_CRITERIA and confidence >= MIN_CONFIDENCE:
                        brief["_jev_topic_group"] = label
                        brief["_jev_topic_confidence"] = round(confidence, 3)
                        report["tagged"] += 1
                    else:
                        report["uncertain"] += 1
                except Exception as e:  # noqa: BLE001 — optional metadata must fail open
                    report["failed"] += 1
                    log.warning("News topic label failed for %s: %s",
                                (brief.get("title") or "")[:60], e)
        return report
    finally:
        if own_client:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass
