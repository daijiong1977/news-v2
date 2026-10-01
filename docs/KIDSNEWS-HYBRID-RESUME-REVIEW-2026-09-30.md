# Kids News 混合流水线：Spec 与实现审查（2026-09-30）

> 2026-10-01修复记录：以下原始审查保留；实施提交 `66b7546cb9705febdfb3855ed06d9d2e1c025111`，仅feature分支，未生产上线。Python 3.10.20相关219项通过，真实VM首测仍待执行。

只读审查 `docs/KIDSNEWS-HYBRID-RESUME-SPEC-2026-09-30.md` 及其 §2 基线。未修改代码、未 commit、未调用模型/网络/数据库/部署。

**基线核对**
- news-v2 `codex/agent-provider-boundary` @ `a1c1670`；Bot `codex/stepwise-full-shadow` @ `a7b9eef`。与 Spec §2 一致。
- 两仓库 `pipeline/ shadow/ supabase/ agent/` 逐文件相同；`UPSTREAM.json` 指向 `a1c1670`。
- 两边工作树只有 Spec 文件本身是未跟踪状态。
- Python 3.10.20：`test_agent_shadow*.py`、`test_ai_providers.py`、`test_publication_bundle.py`、`test_batch_single_repair.py`、`test_shadow_site.py` 共 127 项通过。Deno 测试本次未跑。
- 下文"复现"均为离线假 provider / 假答卷，没有真实调用。

## 总体判断

Spec 方向正确，对现状的描述基本诚实：§1 表格里标"未完成"的两项（HTTP 结果不确定后的同目录恢复、一小时后续跑）我都复现了。

但 Spec 把精力集中在"进程被杀"的理论窗口上，而首测更可能被两个 Spec **没写**的普通问题拦住：

1. 任何一次 DeepSeek 4xx/5xx 都让运行目录永久报 "outcome uncertain"（B1）。
2. News 当天没有 importance≥3 的候选时，补稿会烧光目录和三栏共享的抓取预算（B4）。

建议顺序：先修 B1、B3、B4（B2 随建议 S1 一起解决），再做 S7 原生兜底，补回归测试，再进 VM 首测。B5–B7 可同批修。P 类留到影子通过后。

---

## 1. 首次 Bot 影子运行的阻塞项

### B1　HTTP 任何异常都变成永久 "uncertain"，包括明确没执行的 401/429/5xx

**实施状态：已修复（66b7546）：transport_failure分类、最多3次预算内重试、429上限120秒；错误状态可同目录恢复。测试B1三项及probe_b1。**

- 位置：`pipeline/agent_shadow_providers.py:156-162`（`except Exception` → RuntimeError）、`:125-127`（state=attempting 即拒绝）。
- 复现：假 provider 抛 `requests.HTTPError`(401) → `RuntimeError: HTTP task failed (HTTPError)`；同目录重跑 → `ValueError: HTTP attempt outcome uncertain; do not auto-retry, use a fresh run`。
- 原因：不区分"服务器已回复错误"（请求肯定没生成内容）与"读超时/发送后连接重置"（不确定）。`http-attempt.json` 停在 `attempting`，之后永远拒绝。
- 影响：DeepSeek 一次限流就必须换目录；之前的抓取、图片、五篇初稿全部作废（答卷哈希绑定目录）。Spec §6 写的 "429 按 Retry-After 延迟" 和 "401 同目录暂停、修身份后继续" 都没有实现。
- 修法：按 `requests` 异常分类——
  - `HTTPError`（有 response，4xx/5xx）、发送前的 `ConnectionError`/`ConnectTimeout` → `failed_not_executed`，预算内可自动重试（429 读 `Retry-After`，上限 120 秒，最多 N 次）；
  - `ReadTimeout`、发送后的 reset → `outcome_uncertain`，才需要人工 `recover-task`。
  - 状态文件写明 `error_class`、`http_status`、`retry_after`。
- 回归：`test_http_4xx_is_retryable_in_same_run`、`test_read_timeout_is_uncertain_not_retried`、`test_429_waits_retry_after_within_budget`。

### B2　answer.json 已落盘但 state 未到 complete 时，重跑拒绝已有答案

**实施状态：已修复（66b7546）：原子answer.json是提交记录，优先于attempting；rebuild_audit重建索引。测试test_resume_after_saved_answer_before_http_complete及probe_b2。**

- 位置：`pipeline/agent_shadow_providers.py:159-169`（159 写 answer.json，169 才写 complete）。
- 复现：正常完成后把 `http-attempt.json` 改回 `attempting`（模拟在两次写之间被杀）→ 重跑报 uncertain，尽管 `answer.json` 存在、可解析、request_id 匹配。
- Spec §5.4 已指出，确认属实。修法见 S1。
- 回归：`test_resume_after_saved_answer_before_http_complete`（Spec §9 已列）。

### B3　一小时 wall-clock 后新任务被拒

**实施状态：已修复（66b7546）：取消wall-clock拒绝；超过24小时check_stale要求显式确认及fresh registry，历史重核保留日期和预算。测试test_resume_after_wall_deadline_without_resetting_budget、两项stale测试。**

- 位置：`pipeline/agent_shadow_providers.py:81`、`:135`。
- 复现：`provider-audit.json` 的 `started_unix` 回拨 3700 秒 → 下一个新任务 `Shadow run deadline exhausted; use a fresh directory`。首测 Bot 一次等答卷超一小时即触发。
- 修法见 S2。
- 回归：`test_resume_after_wall_deadline_without_resetting_budget`（Spec §9 已列）。

### B4　News 没有重要稿时，补稿烧光目录和抓取预算（Spec 未提）

**实施状态：已修复（66b7546）：needs仅在还有未尝试改善稿时追重要News/第二Science出版方；每栏12独立抓取预算，耗尽停止该栏补稿。测试test_news_without_important_candidate_stops_after_first_batch、probe_b4及per_category_exhaustion。**

- 位置：`pipeline/agent_shadow_editor.py:65-67`（`needs()` 把缺重要稿当不足）、`:114-117`（过滤后 break 进入 extend）、`pipeline/agent_shadow_batch.py:197-212`（`extend` 只看是否还有未消费候选，不看 importance）。
- 复现（离线 fixture：News 16 篇候选全部 importance=2，其余栏目正常）：
  - News 做了 **4 次 DeepSeek 批量写稿**：`rewrite-batch-News-8/16/24/32`，共写 16 篇初稿；
  - 2 轮 `discover-News-*`；
  - 抓了全部 16 篇 News 正文；
  - 最终仍是 `News has no qualified high-importance story`。
- 影响：真实目录 30 篇时 News 一栏可抓 30 篇，而 `LIMITS["body_fetches"]=36` 是三栏共享，Science/Fun 会 `budget_exhausted`。DeepSeek 写稿费用约 ×4。
- 修法：缺重要稿只在目录中还有**未尝试且 importance≥3** 的候选时才补，否则接受告警；Science 缺第二出版方同理（还有未尝试的不同 publisher 才补）。抓取预算改为每栏（如 12/12/12）。
- 回归：`test_news_without_important_candidate_stops_after_first_batch`（断言：rewrite-batch-News 只 1 次、无 discover、News 抓取 ≤ 8）。

### B5　`validate_batch` 的 News 首稿规则可能让整批 8 篇作废

**实施状态：已修复（66b7546）：最高重要性者被选入时才必须首位；skipped ID单独消费，未选其余原文保留。测试test_batch_skipping_top_importance_does_not_consume_batch。**

- 位置：`pipeline/agent_shadow_batch.py:34-37`。
- 规则要求 DeepSeek 第一篇必须等于 8 篇里 importance 最高者。若该篇原文不适合（DeepSeek 不选它），修正两次后 `AnswerRejected` → `batch-invalid` → **8 篇全部 consumed**，再开下一批。
- 修法：改为"importance 最高者若在 drafts 中必须排第一"，并允许 drafts 附 `skipped:[{id,reason}]`；跳过的 ID 不消费其他 7 篇。
- 回归：`test_batch_skipping_top_importance_does_not_consume_batch`。

### B6　Bot 看到的续跑命令是 `python -m`，不是 `.venv/bin/python`

**实施状态：已修复（66b7546）：next/rerun使用sys.executable并shell quote。test_recovery_cli_single_json_and_exit_codes实际子进程验证单行JSON及exit2→0→1。**

- 位置：`pipeline/agent_shadow.py:80`（`next`）、`:471`（`rerun`）。
- Spec §6 要求恢复输出必须是 `.venv/bin/python`。SKILL 只用文字补救；Bot 照抄 JSON 里的命令会用系统 python（无依赖）。
- 修法：用 `sys.executable` 生成命令。
- 回归：`test_recovery_cli_single_json_and_exit_codes` 中断言 `next`/`rerun` 以 `sys.executable` 开头。

### B7　`status` 既拿锁又校验答卷哈希

**实施状态：已修复（66b7546）：status不拿锁、不写状态；异常作为answer_integrity返回。test_status_without_lock_returns_answer_integrity。**

- 位置：`pipeline/agent_shadow.py:427-428`（所有命令含 status 都在 `run_lock` 内并 `verify_answer_hashes`）。
- Spec §11 把 `status` 列为"安全状态命令"，但 `step` 运行中查 `status` 得到 exit 1 "another command is running"；答卷被改时 `status` 也 exit 1。
- 修法：`status` 无锁、只读；哈希校验结果作为字段 `answer_integrity` 返回，不抛异常。

---

## 2. 不阻塞影子、阻塞生产部署的项

### P1　入库事务删除同日期不在包里的文章，但包允许不满 9 篇

**未修复：用户明确排除本轮生产项；影子验证后另开任务，不能用于批准生产启用。**

- 位置：`supabase/migrations/20261001_bot_publication_handoff.sql:90-96`（delete 同日期不在包内的 stories/search_index）；`pipeline/publication_bundle.py:75`、`bundle.ts:67`（允许 1..9 篇）。
- 注释写 "Full three-section package replaces that date"，但校验不强制。Fun=0 的包会删掉旧 writer 已发布的当日 Fun。
- 修法：生产包强制 counts 3/3/3，或 delete 只针对包内有内容的栏目。

### P2　上传 409 没有比对；`verify` 的 ready 标记不幂等

**未修复：用户明确排除本轮生产项；影子验证后另开任务，不能用于批准生产启用。**

- 位置：`pipeline/publication_bundle.py:210-215`（upload `upsert:'false'`）、`:278-279`（ready 上传）。
- 两处直接抛异常，异常只打印类型名。网络断后重跑同一包会报错，而不是"已存在且哈希一致"。Spec §7/§8 已列为生产前必须，确认未做。
- 修法：409 时 GET 已有对象比对 sha256；一致则视为成功。

### P3　旧生产 writer 与新 worker 并行写 `latest.zip`/站点

**未修复：用户明确排除本轮生产项；影子验证后另开任务，不能用于批准生产启用。**

- Spec §8(8) 已承认。生产前要么禁用 `daily-pipeline.yml` 的 pack/upload，要么 worker 拒绝在旧 writer 时间窗内运行。

### P4　live schema 未验证

**未修复：用户明确排除本轮生产项；影子验证后另开任务，不能用于批准生产启用。**

- `redesign_stories(published_date,category,story_slot)` 唯一约束见 `20260423_redesign_parallel_schema.sql:68`；
- `redesign_search_index(story_id,level)` 唯一约束**在仓库迁移里没找到**（`pipeline/search_index.py:96` 用 `on_conflict=story_id,level`，说明线上应有，但不能从仓库证明）。
- `sql_test.ts` 的 PGlite 表是测试自建的，不是证据。生产前必须在隔离库按 live schema 验证 RPC。

### P5　公开核验要求站点先部署再入库，runbook 没写明前置依赖

**未修复：用户明确排除本轮生产项；影子验证后另开任务，不能用于批准生产启用。**

- `worker.ts:14` 先 `publicMatches` 再写归档：意味着 kidsnews-v2 的 Git PR 合并与 Vercel 部署必须先完成，ready 才能上传。顺序合理，但 `KIDSNEWS-BATCH-AND-ZIP-RUNBOOK.md` 应明确这个顺序。

---

## 3. 可后续优化

实施状态（66b7546）：首答卷answer.attempt-1.json、boundary日志try/except、正文_fetch_audit同原子落盘已修。未选原文沿用下一批是保留原策略，不重复抓取；MAX_TASKS仍120，未调高。两个小项回归见test_boundary_logging_failure_is_nonfatal、test_fetch_audit_survives_crash_after_body_save。

- HTTP 修正覆盖第一次 `answer.json`（`agent_shadow_providers.py:159`）；Spec §5.3 想保留原答卷做质量对比，目前没有。可改名为 `answer.attempt-1.json` 保留。
- `boundary()` 写 `steps.jsonl` 无 try/except（`agent_shadow.py:76`）：`completed-steps.json` 已写，结果不丢，但命令 exit 1 会让 Bot 误以为失败。
- `AutonomousEditor.pool` 的 `fetch_results` 审计只在 `self.save()` 时落盘（`agent_shadow_autonomous.py:197-220`）：被杀后 `bodies.json` 有、审计没有——不影响恢复，影响报告。
- 批量模式里 DeepSeek 没选的 3 篇原文下一批会再送一次（`agent_shadow_batch.py:91-96`）。文档说有意为之，但 DeepSeek 刚拒过它们。
- `MAX_TASKS=120` 对正常约 35 个任务够用；B4 修好前不要调高。

---

## 4. Spec 的矛盾、遗漏与建议

### 矛盾 / 遗漏

- §6 承诺的异常分类（429、401、timeout 区分）与 §5.4 "attempting 一律 uncertain" 互相矛盾；代码按后者实现。应先定分类规则，再定恢复接口。
- §1 表格 "缓存正文/图片、保留合格稿、只补不足栏目 已实现" 正确，但漏掉 B4：补稿**触发条件**本身有问题。
- §3 第 7 行 "最终不足允许少于3篇"——代码在 News 缺重要稿时并不"允许"，而是穷尽目录和 discover。
- §5.5 "超过24小时标记 stale_run" 正确；60 分钟 ×2 的延期机制没有必要（见 S2）。
- §9 测试清单缺 B1、B4、B5、B7 对应的测试；`test_fun_refill_crash_does_not_repick_news_science` 的非崩溃版本已有，崩溃注入版本没有。
- §12 "不得仅凭190/7测试数字认定已满足"——同意；本次 127 项通过不覆盖上面任何一个 B 项。

### 建议（更好的做法）

**实施状态：已修复（66b7546）；答卷与哨兵重建审计，见B2。**

**S1　用答案文件做提交记录，取消 `complete` 状态。**
§5.2 的 intent / unit-result / fsync 五步协议对单进程 CLI 过重。更简单：HTTP 返回后把 `request_id`、`attempt_id`、`revision`、`usage`、`finish_reason`、`content` 原子写进**一个** `answer.json`；`provider-audit.json` 改成可从所有 `answer.json` 重建的索引。恢复规则只有一条："answer.json 存在且 request_id/revision 匹配 → 可信"。B2 自然消失，§5.4 的 raw-response.json 也不需要。`attempting` 只保留为调用前哨兵。

**实施状态：已修复（66b7546）；check_stale及持久预算，见B3。**

**S2　去掉 wall-clock deadline，只留预算和新鲜度。**
任务数、HTTP 次数、抓取数已经限制费用；时间限制只应服务"内容过时"一个目的：超过 24 小时要求显式 `--confirm-stale` 并重新核对七天历史。不要做 +60 分钟 ×2 的手工续期——Bot 不会自己想到去运行它。

**实施状态：分类已修（66b7546）。recover-task手工重发接口未实现：本次选择显式native兜底或同目录暂停，不授权uncertain HTTP再发。**

**S3　异常分类写进代码而不是 runbook。**
见 B1。整组五篇的 `outcome_uncertain` 保持暂停（§5.4(6) 正确）；单篇任务的 uncertain 允许 `recover-task --ack-uncertain`。

**实施状态：已修复（66b7546），见B4。**

**S4　补稿只认"有可能改善"的候选。**
见 B4。抓取预算改每栏。

**未修复：S5不是本次任务清单，保留现有机械校验与modifier；建议后续独立评估数字/引语规则误报。**

**S5　modifier 之后加一道零成本机械校验。**
§3.6 承认"无第三轮审核"，这是儿童站点最薄弱处。三条 Python 能做、不花模型钱：
1. 最终正文中引号内的句子必须在原文中逐字出现；
2. 英文字段无 CJK（已有）；
3. 最终正文出现的数字集合必须是原文数字集合的子集。
能挡住最常见的编造引语和改数字。

**未修复：属于P1生产问题，明确不在本次范围。**

**S6　生产包强制 3/3/3**，或入库 SQL 只替换包内有内容的栏目（P1）。

**实施状态：已修复（66b7546）。四项命名回归及fallback内容修正/四稿请求/mixed站点和ZIP标记通过。默认关；仅传输兜底，连续两轮熔断，真实VM配额未知。**

**S7　DeepSeek 传输失败时由 Bot 原生模型兜底（用户确认 2026-09-30）。**
背景：上一轮纯原生跑完整轮，配额约 10%，质量可接受。兜底是一次性事件，允许那一轮用到 10%，不受日常 ≤3% 目标约束。
代码里已有一半：JSON 语法坏 → 原生只修语法（`review-format-batch`）；单篇结构坏 → 原生修那一篇（`review-repair-draft`）；精修本来就是原生。缺的只是传输层失败的兜底。

触发条件（只有这些）：
1. B1 分类后的 `failed_not_executed` 重试用完；
2. 单篇任务或整组五篇的 `outcome_uncertain`（整组兜底时审计记"可能双重付费"）。
不对**内容失败**兜底：DeepSeek 返回了但字数/结构不对，仍走单篇修复和 modifier，不换模型。

用量限制：
- `prepare --http-fallback native` 显式开启，冻结进 `input.json`；默认关闭，生产和旧 profile 不变。
- 兜底后该任务不再回 DeepSeek；同一轮内所有角色（write / details / detail_review）都可兜底，上限按任务数计入 `MAX_TASKS`，并单独记 `fallback_tasks`。
- 原生写批量时写 4 篇（3 篇 + 1 备用），不写 5 篇，不给 8192 `max_tokens`。
- 兜底导致的配额上限按单轮 10% 衡量；连续两轮都兜底 → 退出 1，要求人工查 key / 账户，不再静默继续。

诚实标记（必须）：
- `provider-audit.json` 该请求记 `fallback: native` 和原始失败原因、分类。
- `review-results.json` 的 `review_method` 对兜底篇目改为"同模型写稿并自检"，不再称"第二模型修稿"。
- `done.json` 和影子站 manifest 的 `provider` 记 `mixed`；报告单列哪几篇是兜底写的。
- `publication_bundle` records 带 `writer_provider`；生产 worker 可拒绝 `native` 写的稿（影子不限）。

实现落点：
- `TaskRouter.complete`：HTTP 分类为失败且开关开、额度有 → 把同一 payload 写成原生 `request.json`（instructions 注明 fallback 和篇数限制），`http-attempt.json` 记 `status: fallback_native`，抛 `AgentNeeded`。之后重跑按原生路径处理；`request_id` 不变，校验函数不变。
- `ask()` 的 `hybrid_http` 自动修正逻辑识别 `fallback_native`，改走 exit 2 让 Bot 修一次。
- 不兜底的：`discovery`、`image_review`（本来就是原生）。

回归：`test_http_failure_falls_back_to_native_once_and_labels_it`、`test_fallback_budget_counts_into_max_tasks`、`test_content_errors_never_trigger_fallback`、`test_two_consecutive_fallback_runs_stop`。

---

## 附：本次复现的三个探针（供写回归测试参考）

| 探针 | 做法 | 结果 |
|---|---|---|
| B1 | 假 `OpenAICompatibleProvider` 抛 HTTPError(401)，同目录重跑同一任务 | 第二次 `outcome uncertain; use a fresh run` |
| B2 | 正常完成后把 `http-attempt.json` 的 status 改回 `attempting`，删 `accepted-answer-hashes.json`，重跑 | `answer.json` 存在仍报 uncertain；HTTP 未重调 |
| B4 | `test_agent_shadow_batch.setup_batch` 基础上把 plan 的 News importance 全改 2，discover 返回空 | 4 次 rewrite-batch-News、2 次 discover、News 抓 16/16 |


## 本次交付验收（2026-10-01）

修复位置：agent_shadow_providers.py（B1/B2/B3/S7路由）、agent_shadow.py（新鲜度/CLI/status/日志/manifest）、agent_shadow_editor.py（B4及逐篇标记）、agent_shadow_autonomous.py（独立抓取预算/抓取审计）、agent_shadow_batch.py（B5及四稿来源标记）、publication_bundle.py（writer_provider）。生产full_round/news_rss_core及P1–P5未改。

测试命令（专用3.10 venv）：
```sh
python -m pytest -q pipeline/test_agent_shadow*.py pipeline/test_batch_single_repair.py pipeline/test_publication_bundle.py pipeline/test_shadow_site.py pipeline/test_ai_providers.py pipeline/test_safety_quality.py pipeline/test_quality_rca.py pipeline/test_wc_repair.py pipeline/test_cadence_calibrate.py
```

Python3.10.20：219项通过（新增29项含参数化/三探针），2个已知依赖/runpy警告。新回归在相应修复前已观察到失败，过程摘要见docs/bugs/2026-10-01-shadow-http-resume.md。纯离线模型/网页/图片/JSON模拟，不能证明真实内容质量、网络稳定性或3%配额。已明确的VM首测前置：拉取本次运行分支、3.10依赖、真实只读7天registry、VM.env的DeepSeek key、原生新会话答题；不发布、不写DB、不发邮件。P1–P5仅阻塞生产，不阻塞本地影子pack。
