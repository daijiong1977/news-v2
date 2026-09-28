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
a ranking bonus. The shared rule also covers spares and legacy carry-over. Actual
college competition and records remain eligible.

## Order of decisions

1. RSS collection and existing forbidden-word/preview checks build the candidate pool.
2. `pipeline/editorial_routing.py` asks Jev which section best fits each probed brief. It moves a brief only when the selected section differs from its feed section **and confidence is at least 0.90**. Uncertain answers and errors retain the feed section. `JEV_ROUTE=on|shadow|off` controls move, observe-only, or bypass; default is `on`.
3. Per the September 27 policy update, dedup compares **within the same section only**: News against News, Science against Science, and Fun against Fun. Each seven-day history normally contains 21 stories. The early filter in `pipeline/full_round.py` drops repeat source URLs and high-similarity titles from that section; `pipeline/jev_rank.py` scores routed candidates, applies its 0.60 category-fit floor and removes detected duplicate events while forming the full candidate catalog. `publication_history.py` then checks potential fresh publication candidates against their entire same-section history without a keyword-overlap gate, including spares and checkpoint resumes. If fewer than three fresh stories survive, Stage 3 searches the full catalog, preferring a different known topic group; only when no qualified alternative survives does it take the best remaining same or unknown group article. Refill does not run another same-day model comparison. When today's supply is exhausted, qualified fresh content can ship short; the mega path does not add yesterday's stories. Same-event dedup is separate from soft topic variety: two independent storms may still run if no eligible alternate topic exists after backfill.
4. `pipeline/news_topics.py` asks Jev for a topic label for the remaining pool. Confidence below 0.70, an error, or `other` leaves the story ungrouped. Labels never reject a brief.
5. Before the curator call, `pipeline/jev_rank.py::for_curator` examines the **full** ranked catalog and may replace a repeated-topic shortlist brief with a different known topic. A reserve must meet the category-fit and Jev quality floors, be within 0.10 editorial-pick points of the displaced brief, preserve source/publisher breadth and important-News count, and already have passed same-event and seven-day history screening. This does not guarantee one brief per topic or add a Jev call. The run log prints the six News shortlist topics and any swap. The curator still ranks up to five from its six News inputs; `pipeline/mega_curator.py` then prefers three different topics in its top three when suitable alternatives exist. Stage 3 retains the full scored candidate catalog: promotion in `pipeline/full_round.py` tries a fresh known topic first, then the best repeated or unknown topic. Every promoted story still passes the independent safety filter.
6. Full-text verification, rewrite, and the **independent full-text child-safety audit** still run. Routing, ranking and topic labels must not replace or weaken that audit.

Science source-diversity alerts start below **two distinct source names** among three final stories; one repeated source is acceptable when topics are varied. News and Fun still alert below three distinct sources. The separate Science goal of at least two *publishers* remains in force, so two ScienceDaily feeds do not count as two independent publishers. Topic-diversity and independent child-safety warnings are unchanged. The digest threshold is in `pipeline/quality_digest.py`; the run warning threshold is in `pipeline/full_round.py`.

## Category and topic map

| Section | Intended stories | Jev topic labels |
| --- | --- | --- |
| News | Government, diplomacy, conflict, severe weather, infrastructure, public health and civic/public-affairs Tech/AI | `us_politics`, `international_relations`, `war_security`, `severe_weather`, `transport_infrastructure`, `public_health`, `science_environment`, `community`, `technology_business`, `sports`, `entertainment`, `other` |
| Science | Physics, chemistry, astronomy, Earth/climate, biology (including animal research), medicine and archaeology | `astronomy_space`, `physics`, `chemistry_materials`, `biology_ecology`, `earth_climate`, `medicine_health`, `fossils_archaeology`, `other` |
| Fun | Playful Tech/AI (robots, inventions, creative uses); non-scientific animal happenings; sports, music, screen entertainment, games, arts, history and kids' achievements | `swimming`, `tennis`, `other_sports`, `music`, `film_tv`, `games`, `arts_books`, `animal_events`, `technology`, `artificial_intelligence`, `history_culture`, `kids_community`, `other` |

Examples: Fat Bear Week is Fun `animal_events`; a biology study of bears or a newly discovered animal species is Science `biology_ecology`. Government AI use, school AI rules and data-center disputes with community consequences are News `technology_business`; an armadillo-inspired robot is Fun `technology`. A star discovery using a telescope remains Science `astronomy_space`. A threatening hurricane is News `severe_weather`; a study of hurricanes is Science `earth_climate`. News labels remain for uncertain/borderline feed items.

旧版记录（9/26，已由下段 9/27 规则修订）：Tech 与 AI 放 Fun；生物学研究、新物种、动物行为、恐龙/动物化石和生态研究保留 Science。动物趣闻、宠物、比赛和有趣的野生动物活动归 Fun。共享定义位于 `editorial_policy.SECTION_POLICY`，同时用于 Jev 路由、栏目适配（含 deep-dig）和主编。`animal_events` 保留旧名称避免破坏历史标签；新增 `technology`、`artificial_intelligence`。旧 `engineering_technology` 仅兼容历史 checkpoint。按主旨判断，提到 AI 工具不意味着一篇化学稿自动变成 AI 新闻。仍保留 0.90 路由置信度和故障回退；不保证每篇都成功识别。购物、招募、低儿童相关性与安全规则不放宽。需从采集重新运行验证，旧 checkpoint 不会自动重新分栏；本次不迁移来源表或历史已发布稿。

用户修订（9/27）：上句「Tech 与 AI 放 Fun」不再作为一刀切规则。**公共事务类 Tech/AI 留 News，趣味科技留 Fun**。例如数据中心争议、AI 与政府网站、科技监管及学校规则归 News；机器人、发明、游戏和创意演示归 Fun。重大政治、政府和外交事件不能只因需要成人背景而被排除；适宜时选一篇最有实际后果的政治/外交报道，用儿童可理解的语言中立重写，独立全文安全审核不变。中美就伊朗、古巴问题交锋应留在 News 候选目录接受重要性、历史事件和安全审查，不等于强制发布。News 仍优先三种不同题材，不靠多篇类似政治报道凑数。

9/27 不发布预览的边界：四篇用户点名的稿件（美国国会监督、数据中心争议、OpenAI 与美国政府网站、中美就伊朗/古巴交锋）都进入 News 候选；明确的 BBC 足球稿进入 Fun，机器人进入 Fun。但 Jev 对这些公共事务稿的 `section_value` 仅约 1.5–1.7，未达到原有高重要性提示门槛 2.5；一次安全阶段复测的 News 三篇仍未达到理想编辑组合。故目前不能把分类通过等同于最终选稿质量通过，也不能只靠调低阈值宣称问题已解决。

后续安全阶段预览（同日、无写入/发布）：News 最终候选是「俄德外交冲突」「英国美军基地附近反恐逮捕」「自主 AI 代理的法律责任」，仍只有两家来源、没有达到高重要性条件；Science 和 Fun 各三篇，Science 来自两家出版方。儿童安全独立审核正常运行并拒绝三篇 News；Fun 有一篇 middle 版本 282 字，低于理想 300–410 字区间。这说明本 PR 改善的是候选分栏及错误补稿防线，**还没有解决 News 最终编辑质量或所有字数问题**。不要仅凭单次预览自动合并或发布。

战争/死亡审稿修订（9/27）：题材不等于文字风险。一句准确、平静的伤亡事实可以让孩子了解战争；残骸/伤情的场景化描写、让孩子想象自己遇袭、恐惧证词和攻击细节仍可能不适合。News 改写和字数修复提示都要求保留必要事实、去掉这些渲染。独立复核仍按**最终 easy/middle 正文**逐项评分，阈值不变；仅当第一次独立评分的拒绝原因属于暴力/恐惧/悲伤/成人背景，且没有粗口、性/药物、偏见或禁词时，才允许一次定向文字修复。修复后必须通过字数/禁词检查和**新一轮独立全文复核**，否则仍拒绝并从候选目录补稿。代码在 `pipeline/news_rss_core.py` 的 `repair_hard_news_safety` 与 `filter_safe_rewrites`。单篇不发布验证中，乌克兰无人机稿第一次被判恐惧 4；改写后保留少年遇难事实、删掉现场渲染和恐惧证词，第二次独立评分为暴力 2/恐惧 3/悲伤 3，符合既有门槛。该结果不代表所有战争稿都会过审。

随后整轮不发布预览：News 最终为美伊谈判、OpenAI 与美国政府网站、曼谷暴雨，三家来源；一次 News 备用稿在修订后通过第二次独立复核。Science/Fun 各三篇。主编对某篇乌克兰无人机原稿仍未列入前五，因此另校准了主编提示：预筛估计稿件**能否被安全改写**，而不是把原稿所有措辞视为必须保留；最终文本仍必须过独立审核。该提示改动只完成至主编阶段的不发布复测，未作为上线证据。前述 Fun 字数偏短和 News 重要性偏低仍是独立问题。

最终代码再次整轮不发布预览：该无人机备用稿首次独立评分恐惧 4；定向修复后的第二次独立评分仍为恐惧 4，因此系统**正确拒绝**，随后从目录补了另一篇安全稿。与上一个单篇通过样本一起看，二次改写有波动，但没有发现绕过独立复核或放宽阈值的路径。不能把“战争题材可以报道”误读为“每一篇战争改写都必须通过”。

补稿防线（9/27）：BBC 等来源的明确 `/sport/`、`/sports/` 文章不能从 News 补稿路径进入；深层同日 feed 不可重新加入首轮已看过的链接；低于栏目 Jev 选稿线的候选不能为了凑够三篇而发布，合格稿不足时保留 1–2 篇。News 每源首轮由 10 提到 12 条，以免第 11–12 条仍新鲜的公共事务稿随 feed 滚动落出采集窗口。调整点为 `editorial_policy.py`、`editorial_routing.py`、`jev_rank.py`、`full_round.py`；先做分栏和编辑测试，再做不发布预览，不能以模型一次评分代替全文安全审核。

### Science → Fun 来源候选（9/17–9/26 feed 快照）

- **Popular Science（source 121，当前启用）**：RSS 返回 58 条。包含 Fat Bear Week、动物趣闻、奇特动物动态和消费科技，能补 Fun 题材；也混有生物发现与购物指南，因此建议转入 Fun 后继续按单篇分栏/禁购物规则筛选。
- **ScienceDaily Top Technology（source 6，当前启用）**：36 条，但近期包括大量 LHC、量子物理、行星、天文等研究。来源名里的 Technology 不代表整条 feed 都属于 Fun，建议留在 Science，由逐稿路由处理明确的 AI/机器人/设备稿。
- **MIT Technology Review（source 110，当前停用）**：feed 可读，但样本含 Pentagon AI 测谎器、边境监控、器官移植等成人政策主题；暂不建议为了填 Fun 而启用。
- **IEEE Spectrum（source 338，当前停用）**：本次 RSS 请求返回 HTTP 403，暂不能作为可用供稿源。

因此当前有证据支持的源级调整只有 Popular Science 一条；若希望至少两条，宜再找一条活跃、专门且可抓取的 AI/Tech feed，不建议把 science-heavy 的整条 feed 一起搬走。生产来源表尚未改动。

Fun sports are split by sport, not by the broad `sports` label: a swimming race and a tennis match can both appear among the three published Fun articles if they are different events and pass all other gates. Diving and water polo belong to `other_sports`. This remains a preference, not a quota: no swimming story is invented or forced into an edition without a suitable candidate. BBC Swimming and BBC Tennis are enabled daily Fun feeds. SwimSwam (source ID 220) was disabled on 2026-09-28 after a low-value coach obituary entered the thin Fun shortlist; its row remains for attribution and probe history. Source selection can skip either BBC feed on a particular day.

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
- Pre-curator topic breadth and 0.10 score-gap tuning: `for_curator` and `TOPIC_SWAP_MAX_PICK_GAP` in `pipeline/jev_rank.py`; soft first-three preference and source-preserving swap: `_prefer_top3_topic_diversity` in `pipeline/mega_curator.py`; candidate refill preference: `promote_spare_and_rewrite` in `pipeline/full_round.py`.
- Same-event and past-seven-day controls: `pipeline/jev_rank.py` (`SAME_STORY_Q`, `SAME_EVENT_Q`, pair-selection and past-event logic). These are distinct from topic labels and should be tested with both duplicate and legitimate-follow-up examples.
- Final safety gate: `filter_safe_rewrites` in `pipeline/full_round.py` and the safety evaluator it calls. Do not skip it based on a Jev section/topic answer.
- Independent safety-vet resilience: `independent_safety_vet` in `pipeline/news_rss_core.py` retries an incomplete batch row as a single article. Other valid independent scores remain in force; only a row still unavailable after retry uses the existing rewriter-score fallback, marked `_independent_vet_status=fallback`. Inspect this count in every run; a fallback is a safety-review warning, not a normal success signal.

## Validation and operations

Run `./.venv/bin/python -m pytest -q pipeline/test_editorial_routing.py pipeline/test_news_topics.py pipeline/test_publication_history.py` for routing, grouping and the history guard, then the relevant full pipeline tests. Inspect telemetry for `section_route`, `jev_rank`, `editorial_topics`, `publication_history`, `enrich`, safety rejects and per-section counts. Spot-check each section against its own seven-day history, along with topic repetition and genuine category fit. Jev calls cost tokens and time; compare actual phase durations and usage with a baseline. Observe the next natural scheduled run after merge unless a manual run is explicitly requested.

For future changes to this live project, create a branch and PR, test and review it, then merge into `main` only with the requested approval. The workflow can be dispatched on a branch for validation; that is not a merge.
# Jev 栏目价值与送审量（PR #69 后续调整）

- News / Science 送主编上限保持 6；Fun 上限改为 **7**。保留池仍为 10，主编最多排 5、首批改写 4、最终发布 3；不是把改写量提高到 7。低分或不合格候选不足时，不强凑 7。
- `pipeline/jev_prefilter.py` 在同一次预筛请求中新增 `recruiting` 语义判断，≥0.90 提前排除大学体育招募/承诺/转学通道稿。它不受软性「保留 8 篇」保护；shadow 只记录、off 不执行，Jev 故障维持既有回退。正则规则仍是另一路防线。
- `pipeline/jev_rank.py` 在原有逐稿评分请求中新增 `section_value`（0–4）：News 为对美国/美国儿童的实际重要性；Science 为科学发现与学习价值；Fun 为真实儿童趣味。标准见 `SECTION_VALUE_LEVELS`，不能把美国地名、名人或煽动标题当作重要性。
- 3/4 分分别给予 0.10/0.18 排名加分；与已有体育加分取最大值，不叠加。Fun ≤1 分不会进入主编、备用池或 deep-dig 补稿，即使池薄也不恢复；未知/失败评分不冒充低趣味评分，保留现有故障回退。
- News：重要性 ≥2.5、编辑 pick 不低于栏目线、栏目适配 ≥0.60 的候选优先进送审池，仍受事件去重等硬规则约束。主编被要求保留至少一篇；代码对主编返回候选、最终安全候选再次重排。若最终没有，记录告警。不会凭重要性跳过安全门禁，也不保证在候选缺失、主编剔除或安全拒绝后一定凑到一篇。
- 该优先项可能在必要时让位于一篇重要报道，而不是强保三个 feed/题材。Science 两出版方规则不变。对 News 的判断基于后果与儿童相关性，不能按党派、政治立场或对政策的赞同加分。
- `section_value` 会写入 `_jev_rank`、送主编日志及主编输入。阈值集中在上述两个文件和 `pipeline/editorial_policy.py`；调整后运行 `test_editorial_value.py` 及离线全套。
- 不新增逐稿模型请求轮次，但每次请求的输入/输出会略增；实际 token、耗时和编辑效果须在新一轮模型运行中衡量，不能声称免费或已验证提升。
