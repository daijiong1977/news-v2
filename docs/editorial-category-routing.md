# Editorial section routing and topic diversity

This page is the tuning map for the daily News / Science / Fun pipeline. A section is where a story is published; a topic is only a *soft* way to diversify the first three picks within that section. Neither is an event-identity or child-safety verdict.

For actual source counts, every pool boundary, per-section run statistics and
timing, see the [Sep-26 pipeline funnel audit](pipeline-funnel-audit-2026-09-26.md).
Its baseline and subsequent policy changes are recorded separately.

Science now targets at least two qualified publishers, grouping ScienceDaily
feeds together. The preference applies before rewrite and again among safe
finalists; unavailable alternatives produce an explicit warning. Publisher
identity and the final preference live in `pipeline/editorial_policy.py`.
Physics and chemistry are existing topic labels, not guaranteed daily slots.

College recruiting, verbal commitments, recruiting rankings and transfer-portal
announcements are excluded editorial types, not merely sports stories without
a ranking bonus. The shared rule also covers spares and carry-over. Actual
college competition and records remain eligible.

## Order of decisions

1. RSS collection and existing forbidden-word/preview checks build the candidate pool.
2. `pipeline/editorial_routing.py` asks Jev which section best fits each probed brief. It moves a brief only when the selected section differs from its feed section **and confidence is at least 0.90**. Uncertain answers and errors retain the feed section. `JEV_ROUTE=on|shadow|off` controls move, observe-only, or bypass; default is `on`.
3. The early seven-day cross-section filter in `pipeline/full_round.py` drops exact-repeat source URLs (ignoring RSS tracking parameters) and high-similarity titles before paying for body fetch or Jev calls. `pipeline/jev_rank.py` then scores each candidate in its *resulting* section, enforces its 0.60 category-fit floor, checks likely same-event pairs and published stories in **all sections over the previous 7 days**, then narrows the pool. That event check is separate from topic diversity: two angles/stages of one event must combine or one must go; two unrelated storms may both run if the edition needs them.
4. `pipeline/news_topics.py` asks Jev for a topic label for the remaining pool. Confidence below 0.70, an error, or `other` leaves the story ungrouped. Labels never reject a brief.
5. `pipeline/mega_curator.py` uses labels to prefer three different topics in each section when suitable alternatives exist. It preserves hard same-event and source-diversity rules. Stage-3 candidate promotion in `pipeline/full_round.py` also prefers a fresh topic, but can use a repeated topic rather than leave a slot empty.
6. Full-text verification, rewrite, and the **independent full-text child-safety audit** still run. Routing, ranking and topic labels must not replace or weaken that audit.

## Category and topic map

| Section | Intended stories | Jev topic labels |
| --- | --- | --- |
| News | Government, diplomacy, conflict, severe weather, infrastructure and public-health events | `us_politics`, `international_relations`, `war_security`, `severe_weather`, `transport_infrastructure`, `public_health`, `science_environment`, `community`, `technology_business`, `sports`, `entertainment`, `other` |
| Science | Research and discoveries in nature, space, health and technology | `astronomy_space`, `physics`, `chemistry_materials`, `biology_ecology`, `earth_climate`, `medicine_health`, `engineering_technology`, `fossils_archaeology`, `other` |
| Fun | Sports, music, screen entertainment, games, arts, animal events, history and kids' achievements | `swimming`, `tennis`, `other_sports`, `music`, `film_tv`, `games`, `arts_books`, `animal_events`, `history_culture`, `kids_community`, `other` |

Examples: Fat Bear Week is a Fun `animal_events` story; a study of bears is Science `biology_ecology`; a threatening hurricane is News `severe_weather`; a study of hurricanes is Science `earth_climate`. The News `sports` and `entertainment` labels remain for uncertain/borderline feed items, but confident routing should usually move those to Fun.

Fun sports are split by sport, not by the broad `sports` label: a swimming race and a tennis match can both appear among the three published Fun articles if they are different events and pass all other gates. Diving and water polo belong to `other_sports`. This remains a preference, not a quota: no swimming story is invented or forced into an edition without a suitable candidate. SwimSwam is an enabled Fun feed in the live source registry (two-day cadence); BBC Tennis is also enabled (daily cadence). Source selection can skip either feed on a particular day.

### Swimming and tennis news value

For Fun briefs only, the existing per-brief Jev ranking call also scores `sports_priority` (0-4). This adds **no extra API call**. Scores 0-2 do not change the rank; score 3 adds 0.10 and score 4 adds 0.18 to the editorial pick score (capped at 1.0). The raw pick and priority are both retained in `_jev_rank` for inspection. The bonus is soft: source and same-event rules still apply, and category fit plus independent full-text safety still gate publication.

- **4 — highest:** a newly broken world swimming record; Olympic or World Championship title; a Grand Slam champion or final result; or a comparable fresh landmark by a swimming/tennis star.
- **3 — high:** a major international meet, consequential Grand Slam round, national record, or a concrete new star achievement.
- **2 — normal:** a timely but ordinary result or meaningful update.
- **0-1 — no boost:** college recruiting, routine training/profile pieces, an old match repackaged as a new interview, or other sports/non-sports. A famous athlete's name alone is not a new development.

The mega-curator sees the high `sports_priority` annotation and uses the same preference when ranking the final Fun candidates. It is not a required daily swimming/tennis slot. Tune `SPORTS_PRIORITY_LEVELS` and `SPORTS_PRIORITY_BONUS` in `pipeline/jev_rank.py` and the Fun ranking instruction in `pipeline/mega_curator.py`; compare real high/low examples before changing the bonus. If the raw Jev rank stage is disabled or unavailable, the curator still has the prose preference but no numeric bonus.

## Where to tune

- Section definitions and 0.90 move threshold: `SECTION_CRITERIA`, `SECTION_INSTRUCTIONS`, `MIN_MOVE_CONFIDENCE` in `pipeline/editorial_routing.py`. Increase the threshold if false moves appear; use `JEV_ROUTE=shadow` to collect proposals without moving stories, or `off` for immediate rollback.
- Topic definitions and 0.70 label threshold: `TOPICS_BY_CATEGORY` and `MIN_CONFIDENCE` in `pipeline/news_topics.py`. Changing labels means checking prompt, logs, tests and historical comparison; keep `other` ungrouped.
- Soft first-three preference and source-preserving swap: `_prefer_top3_topic_diversity` in `pipeline/mega_curator.py`; candidate refill preference: `promote_spare_and_rewrite` in `pipeline/full_round.py`.
- Same-event and past-seven-day controls: `pipeline/jev_rank.py` (`SAME_STORY_Q`, `SAME_EVENT_Q`, pair-selection and past-event logic). These are distinct from topic labels and should be tested with both duplicate and legitimate-follow-up examples.
- Final safety gate: `filter_safe_rewrites` in `pipeline/full_round.py` and the safety evaluator it calls. Do not skip it based on a Jev section/topic answer.
- Independent safety-vet resilience: `independent_safety_vet` in `pipeline/news_rss_core.py` retries an incomplete batch row as a single article. Other valid independent scores remain in force; only a row still unavailable after retry uses the existing rewriter-score fallback, marked `_independent_vet_status=fallback`. Inspect this count in every run; a fallback is a safety-review warning, not a normal success signal.

## Validation and operations

Run `./.venv/bin/python -m pytest -q pipeline/test_editorial_routing.py pipeline/test_news_topics.py` for routing and grouping, then the relevant full pipeline tests. Inspect run telemetry for `section_route`, `jev_rank`, `editorial_topics`, `enrich`, safety rejects and per-section counts. Spot-check every move and the published first three in each section for cross-section event duplicates, topic repetition and genuine category fit. Jev calls cost tokens and time, so compare phase durations and counts with a baseline before widening the probe pool or adding extra calls. A manual dated run can use the workflow's `run_date` input; make sure it is the intended US editorial date when UTC has already crossed midnight.

For future changes to this live project, create a branch and PR, test and review it, then merge into `main` only with the requested approval. The workflow can be dispatched on a branch for validation; that is not a merge.
