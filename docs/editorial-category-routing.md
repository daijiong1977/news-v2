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
| Science | Physics, chemistry, astronomy, Earth/climate, plant/human biology, medicine and archaeology | `astronomy_space`, `physics`, `chemistry_materials`, `biology_ecology`, `earth_climate`, `medicine_health`, `fossils_archaeology`, `other` |
| Fun | All animal, technology and AI stories, plus sports, music, screen entertainment, games, arts, history and kids' achievements | `swimming`, `tennis`, `other_sports`, `music`, `film_tv`, `games`, `arts_books`, `animal_events`, `technology`, `artificial_intelligence`, `history_culture`, `kids_community`, `other` |

Examples: Fat Bear Week AND a study of bears are Fun `animal_events`; AI in schools is Fun `artificial_intelligence`; a new telescope instrument is Fun `technology`, while a star discovery using a telescope remains Science `astronomy_space`. A threatening hurricane is News `severe_weather`; a study of hurricanes is Science `earth_climate`. News labels remain for uncertain/borderline feed items, but confident routing moves animal/technology/AI-centered stories to Fun, including policy and research.

用户更新（9/26）：动物、Tech、AI 统一放到兴趣栏，不再区分「动物趣闻」和「动物研究」。共享定义位于 `editorial_policy.SECTION_POLICY`，同时用于 Jev 路由、栏目适配（含 deep-dig）和主编。`animal_events` 保留旧名称避免破坏历史标签；新增 `technology`、`artificial_intelligence`。旧 `engineering_technology` 仅兼容历史 checkpoint。按主旨判断，提到 AI 工具不意味着一篇化学稿自动变成 AI 新闻。仍保留 0.90 路由置信度和故障回退；不保证每篇都成功识别。趣味评分承认动物/技术的探索价值，但购物、招募、低儿童相关性与安全规则不放宽。需从采集重新运行验证，旧 checkpoint 不会自动重新分栏；本次不迁移来源表或历史已发布稿。

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
# Jev 栏目价值与送审量（PR #69 后续调整）

- News / Science 送主编上限保持 6；Fun 上限改为 **7**。保留池仍为 10，主编最多排 5、首批改写 4、最终发布 3；不是把改写量提高到 7。低分或不合格候选不足时，不强凑 7。
- `pipeline/jev_prefilter.py` 在同一次预筛请求中新增 `recruiting` 语义判断，≥0.90 提前排除大学体育招募/承诺/转学通道稿。它不受软性「保留 8 篇」保护；shadow 只记录、off 不执行，Jev 故障维持既有回退。正则规则仍是另一路防线。
- `pipeline/jev_rank.py` 在原有逐稿评分请求中新增 `section_value`（0–4）：News 为对美国/美国儿童的实际重要性；Science 为科学发现与学习价值；Fun 为真实儿童趣味。标准见 `SECTION_VALUE_LEVELS`，不能把美国地名、名人或煽动标题当作重要性。
- 3/4 分分别给予 0.10/0.18 排名加分；与已有体育加分取最大值，不叠加。Fun ≤1 分不会进入主编、备用池或 deep-dig 补稿，即使池薄也不恢复；未知/失败评分不冒充低趣味评分，保留现有故障回退。
- News：重要性 ≥3、原始 pick ≥0.40、栏目适配 ≥0.60 的候选优先进送审池，仍受事件去重等硬规则约束。主编被要求保留至少一篇；代码对主编返回候选、最终安全候选再次重排。若最终没有，记录告警。不会凭重要性跳过安全门禁，也不保证在候选缺失、主编剔除或安全拒绝后一定凑到一篇。
- 该优先项可能在必要时让位于一篇重要报道，而不是强保三个 feed/题材。Science 两出版方规则不变。对 News 的判断基于后果与儿童相关性，不能按党派、政治立场或对政策的赞同加分。
- `section_value` 会写入 `_jev_rank`、送主编日志及主编输入。阈值集中在上述两个文件和 `pipeline/editorial_policy.py`；调整后运行 `test_editorial_value.py` 及离线全套。
- 不新增逐稿模型请求轮次，但每次请求的输入/输出会略增；实际 token、耗时和编辑效果须在新一轮模型运行中衡量，不能声称免费或已验证提升。
