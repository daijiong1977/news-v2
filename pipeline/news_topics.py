"""Optional Jev editorial-topic labels for soft diversity in each section."""
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
SCIENCE_TOPIC_CRITERIA = {
    "astronomy_space": "Astronomy, the moon, planets, stars, galaxies or space missions",
    "physics": "Physics, forces, energy, particles, light or fundamental physical laws",
    "chemistry_materials": "Chemistry, molecules, reactions, materials or new substances",
    "biology_ecology": "Animal and plant biology, animal behavior, new species, ecosystems, evolution or biological research",
    "earth_climate": "Geology, oceans, weather science, Earth systems or climate research",
    "medicine_health": "Medical research, human biology, disease mechanisms or treatments",
    "fossils_archaeology": "Fossils, dinosaurs, archaeology or ancient-life discoveries",
    "other": "Science story that fits none of the groups above",
}
FUN_TOPIC_CRITERIA = {
    "swimming": "Competitive swimming, swimmers, swim meets, swimming races or pool/open-water swim records; not diving or water polo",
    "tennis": "Tennis players, matches, tournaments, rankings or tennis organisations",
    "other_sports": "Sports other than swimming or tennis, including football, basketball, diving and water polo",
    "music": "Songs, performers, concerts, albums or music competitions",
    "film_tv": "Movies, television, shows, actors or animation",
    "games": "Video games, board games, puzzles or play",
    "arts_books": "Books, art, theatre, comics or creative projects",
    "animal_events": "Pets, animal contests, unusual animal activities or amusing wildlife events such as Fat Bear Week; biology and animal research stay in Science",
    "technology": "Technology, engineering applications, robotics, inventions, devices, software or technology policy/business; AI uses artificial_intelligence",
    "artificial_intelligence": "AI research, applications, models, AI in schools, AI policy or AI business; choose this over technology when AI is central",
    "history_culture": "History, cultural traditions, museums or heritage",
    "kids_community": "Children's achievements, schools, community projects or uplifting human-interest",
    "other": "Fun story that fits none of the groups above",
}
TOPICS_BY_CATEGORY = {"News": TOPIC_CRITERIA,
                      "Science": SCIENCE_TOPIC_CRITERIA,
                      "Fun": FUN_TOPIC_CRITERIA}
ALL_TOPIC_LABELS = set().union(*(set(criteria) for criteria in TOPICS_BY_CATEGORY.values())) | {"engineering_technology"}  # legacy checkpoints
MIN_CONFIDENCE = 0.70


def topic_group(brief: dict) -> str:
    """Only confident known labels participate in the soft diversity preference."""
    label = brief.get("_jev_topic_group") or ""
    # "other" is a catch-all, not a coherent topic. Never treat two unrelated
    # miscellaneous stories as a duplicate editorial group.
    return label if label in ALL_TOPIC_LABELS and label != "other" else ""


def tag_topics(category: str, briefs: list[dict], client=None) -> dict:
    """Tag one section's briefs; errors/uncertainty leave them ungrouped.

    This never rejects an article. Same-event dedup and the independent final
    full-text child-safety review remain separate, stronger gates.
    """
    report = {"tagged": 0, "uncertain": 0, "failed": 0}
    if category not in TOPICS_BY_CATEGORY:
        raise ValueError(f"unknown editorial category: {category}")
    if not briefs:
        return report
    own_client = client is None
    if own_client:
        client, why = make_client()
        if client is None:
            log.warning("%s topic labels unavailable (%s); keeping original order", category, why)
            report["failed"] = len(briefs)
            return report
    try:
        try:
            from typesafe_sdk import Choice
        except ImportError as e:
            log.warning("%s topic labels unavailable (%s); keeping original order", category, e)
            report["failed"] = len(briefs)
            return report

        instructions = (
            f"Choose the PRIMARY editorial topic for this {category} brief. "
            "Different events on the same broad topic share a label; this is "
            "not a same-event or child-safety judgment. Choose exactly one "
            "label. Animal research/new species/behavior/ecology use Science biology_ecology; "
            "Fat Bear Week and non-scientific animal happenings use Fun animal_events. "
            "Technology uses Fun technology; AI uses Fun artificial_intelligence. "
            "Within Fun, swimming and tennis are separate from other_sports."
        )
        question = {"topic": Choice(instructions=instructions,
                                    criteria=TOPICS_BY_CATEGORY[category])}

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
                    if label in TOPICS_BY_CATEGORY[category] and confidence >= MIN_CONFIDENCE:
                        brief["_jev_topic_group"] = label
                        brief["_jev_topic_confidence"] = round(confidence, 3)
                        report["tagged"] += 1
                    else:
                        report["uncertain"] += 1
                except Exception as e:  # noqa: BLE001 — optional metadata must fail open
                    report["failed"] += 1
                    log.warning("%s topic label failed for %s: %s", category,
                                (brief.get("title") or "")[:60], e)
        return report
    finally:
        if own_client:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass


def tag_news_topics(briefs: list[dict], client=None) -> dict:
    """Backwards-compatible wrapper for the original News-only caller."""
    return tag_topics("News", briefs, client=client)
