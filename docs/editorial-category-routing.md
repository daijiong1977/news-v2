# Editorial section routing and topic diversity

This page is the tuning map for the daily News / Science / Fun pipeline. A section is where a story is published; a topic is only a *soft* way to diversify the first three picks within that section. Neither is an event-identity or child-safety verdict.

## Order of decisions

1. RSS collection and existing forbidden-word/preview checks build the candidate pool.
2. `pipeline/editorial_routing.py` asks Jev which section best fits each probed brief. It moves a brief only when the selected section differs from its feed section **and confidence is at least 0.90**. Uncertain answers and errors retain the feed section. `JEV_ROUTE=on|shadow|off` controls move, observe-only, or bypass; default is `on`.
3. `pipeline/jev_rank.py` scores each candidate in its *resulting* section, enforces its 0.60 category-fit floor, checks likely same-event pairs and published stories in **all sections over the previous 7 days**, then narrows the pool. That event check is separate from topic diversity: two angles/stages of one event must combine or one must go; two unrelated storms may both run if the edition needs them.
4. `pipeline/news_topics.py` asks Jev for a topic label for the remaining pool. Confidence below 0.70, an error, or `other` leaves the story ungrouped. Labels never reject a brief.
5. `pipeline/mega_curator.py` uses labels to prefer three different topics in each section when suitable alternatives exist. It preserves hard same-event and source-diversity rules. Stage-3 candidate promotion in `pipeline/full_round.py` also prefers a fresh topic, but can use a repeated topic rather than leave a slot empty.
6. Full-text verification, rewrite, and the **independent full-text child-safety audit** still run. Routing, ranking and topic labels must not replace or weaken that audit.

## Category and topic map

| Section | Intended stories | Jev topic labels |
| --- | --- | --- |
| News | Government, diplomacy, conflict, severe weather, infrastructure and public-health events | `us_politics`, `international_relations`, `war_security`, `severe_weather`, `transport_infrastructure`, `public_health`, `science_environment`, `community`, `technology_business`, `sports`, `entertainment`, `other` |
| Science | Research and discoveries in nature, space, health and technology | `astronomy_space`, `physics`, `chemistry_materials`, `biology_ecology`, `earth_climate`, `medicine_health`, `engineering_technology`, `fossils_archaeology`, `other` |
| Fun | Sports, music, screen entertainment, games, arts, animal events, history and kids' achievements | `sports`, `music`, `film_tv`, `games`, `arts_books`, `animal_events`, `history_culture`, `kids_community`, `other` |

Examples: Fat Bear Week is a Fun `animal_events` story; a study of bears is Science `biology_ecology`; a threatening hurricane is News `severe_weather`; a study of hurricanes is Science `earth_climate`. The News `sports` and `entertainment` labels remain for uncertain/borderline feed items, but confident routing should usually move those to Fun.

## Where to tune

- Section definitions and 0.90 move threshold: `SECTION_CRITERIA`, `SECTION_INSTRUCTIONS`, `MIN_MOVE_CONFIDENCE` in `pipeline/editorial_routing.py`. Increase the threshold if false moves appear; use `JEV_ROUTE=shadow` to collect proposals without moving stories, or `off` for immediate rollback.
- Topic definitions and 0.70 label threshold: `TOPICS_BY_CATEGORY` and `MIN_CONFIDENCE` in `pipeline/news_topics.py`. Changing labels means checking prompt, logs, tests and historical comparison; keep `other` ungrouped.
- Soft first-three preference and source-preserving swap: `_prefer_top3_topic_diversity` in `pipeline/mega_curator.py`; candidate refill preference: `promote_spare_and_rewrite` in `pipeline/full_round.py`.
- Same-event and past-seven-day controls: `pipeline/jev_rank.py` (`SAME_STORY_Q`, `SAME_EVENT_Q`, pair-selection and past-event logic). These are distinct from topic labels and should be tested with both duplicate and legitimate-follow-up examples.
- Final safety gate: `filter_safe_rewrites` in `pipeline/full_round.py` and the safety evaluator it calls. Do not skip it based on a Jev section/topic answer.

## Validation and operations

Run `./.venv/bin/python -m pytest -q pipeline/test_editorial_routing.py pipeline/test_news_topics.py` for routing and grouping, then the relevant full pipeline tests. Inspect run telemetry for `section_route`, `jev_rank`, `editorial_topics`, `enrich`, safety rejects and per-section counts. Spot-check every move and the published first three in each section for cross-section event duplicates, topic repetition and genuine category fit. Jev calls cost tokens and time, so compare phase durations and counts with a baseline before widening the probe pool or adding extra calls. A manual dated run can use the workflow's `run_date` input; make sure it is the intended US editorial date when UTC has already crossed midnight.

For future changes to this live project, create a branch and PR, test and review it, then merge into `main` only with the requested approval. The workflow can be dispatched on a branch for validation; that is not a merge.
