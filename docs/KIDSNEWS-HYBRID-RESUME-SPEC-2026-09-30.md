# Kids News 混合流水线：完整 Spec、实现与断点恢复方案

> 2026-10-01实施状态：B1–B7/S7已进入影子修复与离线回归；本文件末尾的“审查实施增补”
> 优先于原稿一小时期限/状态协议。实际提交和测试以同名REVIEW修复记录为准，VM真实首测仍待执行。

文档日期：2026-09-30（America/New_York）。
状态：**本地审查草案，不是“全部完成”的声明，也不是 Bot 立即执行的上线指令。**
本轮只写文档，不修改代码、不 commit/push、不调用模型、数据库写、部署或邮件。
审查并修复首测阻塞项之后，才能把最终 runbook 交给 Bot。

## 1. 一句话结论与真实完成度

采用 Python 管机械流程、DeepSeek 做批量初稿和详情、Grok 做编辑判断与单篇 modifier。
保留可恢复的运行目录；一次故障不能丢掉已经完成的采集、初稿和合格稿。
“继续同一轮”不等于“盲目重发远端操作”，更不等于“所有异常都吞掉继续发布”。

| 项目 | 当前证据 | 是否结束 |
|---|---|---|
| opt-in batch-deepseek 8→5→3 | 两仓库代码、离线九篇打包 | 已实现，真实新模式仍待测 |
| 单篇格式/内容修正，不重写整组五篇 | 单 ID 修正与 HTTP 批量调用次数回归 | 已实现正常答卷路径；失联路径另审 |
| 状态原子保存、运行锁、答卷哈希 | 已有实现与离线测试 | 正常恢复已有；强杀窗口未全覆盖 |
| 缓存正文/图片、保留合格稿、只补不足栏目 | 离线测试 | 已实现；实际中断注入待补 |
| HTTP 结果不确定后的同目录恢复 | 现代码要求 fresh run | **未完成，首测前必须修** |
| 超过一小时后的同目录受控续跑 | 现代码按 elapsed wall time 拒绝新请求 | **未完成，首测前必须修** |
| ZIP / ready / 定时消费者与 DB 事务 | Python ZIP + Deno + PGlite | 已实现离线合同，云端未部署/启用 |
| Supabase uploader RLS / 定时 / 归档兼容 | 尚未 live 集成验收 | 生产前必须完成 |
| 实际 Grok 周配额 ≤3% | 旧混合测试观察，不是新模式账单 | 未验证，不能由任务数直接推算 |
| 自动清中间文件 | 用户要求这几天保留 | 暂不启用 |

既有证据：Python 3.10 两仓库相关 suite 各 190 项通过，Deno 各 7 项通过；
另一次断点/修稿/原生交接相关子集 38 项通过。这些不是本草案的新恢复方案验收结果。
实际只读采集：32 个启用来源；同栏过去七天历史 21/21/21；
元数据候选 News 46、Science 27、Fun 35；停在 native plan，没有进行该批真实模型全轮。

## 2. 仓库、目录、基线与职责

| 职责 | 本地 | GitHub / 分支 | 审查基线 |
|---|---|---|---|
| 共享源码，先改这里 | /Users/jiong/myprojects/news-v2-agent-provider | daijiong1977/news-v2 · codex/agent-provider-boundary · PR #86 | a1c167022b4da1662bfaaa1b54fbe8b244576325 |
| Bot 运行快照，最后导出 | /Users/jiong/myprojects/grokbot/grokbot-kidsnews | daijiong1977/grokbot-kidsnews · codex/stepwise-full-shadow · PR #1 | a7b9eef186d1951998c6d77210dd5e2d0ff77404 |
| 网站部署仓库 | 以其项目文档及 git remote 实查为准，本草案不修改 | daijiong1977/kidsnews-v2 | 不假定本机路径/最新 SHA |
| Bot VM | /workspace/kidsnews-shadow | 从上面 Bot 运行分支 pull | 不使用旧 bootstrap main |
| 正式网站 | kidsnews.21mins.com / news.6ray.com | 现有网站 Action / Vercel | 本次未发布 |

PR：https://github.com/daijiong1977/news-v2/pull/86
及 https://github.com/daijiong1977/grokbot-kidsnews/pull/1 。

UPSTREAM.json 固定共享源码 SHA。改动先在共享源码、测试、feature PR；
再导出快照、逐文件比对、重新测试。不要在两处分别维护不同实现。
两个仓库 AGENTS.md 均必须遵循，禁止直接推 main；本草案不授权 merge。
已完成答卷和数据不得因换会话而重写；恢复时不 git pull 到不兼容代码。
本机历史 cwd /Users/jiong/myprojects/kidsnews 不存在，不要再把它当新源码位置。

## 3. 端到端流程与每层输入

| 阶段 | 执行者 | 输入与输出 | 必须保留/检查 |
|---|---|---|---|
| 0 配置快照 | Python / Supabase SELECT 连接器 | 启用来源、D-7≤日期<D 的本栏历史 | 非空历史、项目、日期、来源 ID；新轮刷新，续跑冻结 |
| 1 摘要采集 | Python | RSS/HTML 列表标题、摘要、日期、来源 URL | 先不逐篇抓全文；机械 URL/相同标题去重 |
| 2 编辑初筛 | Grok native plan | 搬栏、题材、同栏事件去重、重要性/趣味性；每栏最多30候选目录 | 保留完整可用备用目录，不只保留6篇 |
| 3 原文与图 | Python | 按目录顺序按需抓到每栏最多8篇合格原文；同页提图并验尺寸/缓存 | 一页取正文和图 metadata；预算、原文词数、历史资格、图片哈希 |
| 4 五篇初稿 | DeepSeek | 每栏一次从八篇选最多五篇并写正文及卡片，不生成详情 | 冻结 ID、理由和初稿；每栏五篇只生成一次 |
| 5 五选三 | Grok | 只看五篇初稿+来源 metadata 排三篇及备用顺序 | 不重复送五份原文；News 第一篇重要性优先 |
| 6 单篇精修 | Grok modifier | 所选稿+该篇原文；修改归因、引语、限定语、长度、事实与中立表达 | 第二模型修稿并自检，无第三轮全文审核；不是独立审核自己修改后的稿 |
| 7 单篇替换 | Python + 对应模型任务 | 不合格先用同批剩余两篇；不够再沿本栏目录取备用 | 只处理不足栏目，不重写已通过稿；最终不足允许少于3篇，不搬昨天稿 |
| 8 最终详情 | DeepSeek + Python | 仅最终三篇/栏生成详情，DeepSeek逐字段/题复核，Python关键词/选项检查 | 不能使用修稿前的旧正文生成详情；不是整组五篇做详情 |
| 9 本地成品 | Python | listing/details/images/site + report + ZIP | 字数、ID、图片解码/大小/hash、source usage、非空成品 |
| 10 网站交接 | 既有 Git / Action / Vercel | 将同份包的静态内容交给既有网站路径 | stage只是新目录，不自动推生产；Action保持不变 |
| 11 Supabase 交接 | Bot Python 上传 | immutable ZIP 到私有 pending；公开核验后上传 ready | 不直写 DB、不调用 Edge；不用 service-role |
| 12 定时入库/归档 | 专用 Edge worker | 校验 ready/包/公开站点；归档+DB事务+index+done | 权限/lease/旧revision保护/幂等；详见第8节 |

正常三栏：3 次 DeepSeek 批量正文、9 次详情、9 次详情复核；
原生约 1 plan + 3 selection + 9 modifier。额外修正、补选与发现单独计量。
这些是任务结构，不是实际费用/时间保证。生产旧 full_round 不切到新模式。

## 4. 编辑质量约束（沿用现有合同）

- News：先选一篇最重要合格新闻，另外两篇再兼顾不同题材与出版方。
  成人政治、战争、死亡不是主题级自动禁用；最终稿不得出现不适合儿童的暴力细节。
- 公共事务科技/AI/政策争议留 News；机器人、发明、趣味科技放 Fun。
  非科研动物趣事进 Fun；biology/动物科研留 Science；政府相关熊猫事件可留 News。
- Science：physics、chemistry_materials、astronomy、biology 等细分题材分别记录。
  优先不同题材和至少两家独立出版方。不同 feed 不等于不同 publisher；
  三篇两家来源本身不报来源不足，不能把同一 ScienceDaily 三feed算三家。
- Fun：实际趣味性；swimming / tennis / other_sports 分开。世界赛事/纪录/明星优先；
  不因候选少而选大学招募、普通大学泳队或教练讣闻。SwimSwam 非活跃；BBC Swimming 保留机会。
- 同事件：News/Science/Fun 各自只与本栏 D 前七天已发布事件/URL比较，同日重跑覆盖不查自己。
  不把更早的长活动去重扩窗当作本轮必修；用户要求先记录。
- 题材/来源多样性是组合偏好，不得替代事实、安全和事件资格；不同 topic 不是语义查重证明。
  主目录应做同日事件去重；补稿阶段不额外反复做同日模型查重。
- 单篇精修必须依据原文；补两方观点只能用有出处的信息，不能编造“另一方说”来凑中立。
- 图片沿用来源图机械检查，不新增昂贵视觉任务；解码成功不代表视觉相关性/版权已认证。
  不合格图省略，重要正文不因缺图淘汰。
- 不改变生产 wordcount_policy。影子 Fun 短源可较短；实际上下限读取
  pipeline/agent_shadow_lengths.py，并保持 prompt、modifier、pack、Edge 一致。

## 5. 断点恢复：必须达到的合同

### 5.1 唯一运行身份

运行身份 = publication date + run directory + frozen inputs/config + code compatibility version。
真正从头再做是另一 run，必须明确授权；不能通过删状态或换目录“修复”普通异常。
暂停数小时/重开 Agent 会话/进程被杀，仍继续原 run-dir；
今天保留全部 debug 中间文件，不能自动清除恢复依赖。

同一目录有锁；OS 进程退出自动释放 flock。不得删锁文件来绕过活进程。
记录 source/runtime SHA 和状态 schema version；恢复前检查代码兼容性。
旧 state 的升级先保留原文件并做明确版本迁移，不重置已用预算。

### 5.2 保存顺序与多文件一致性（待实现加固）

atomic rename 防半个 JSON，但不能保证多个 JSON 是同一个事务；
os.replace 本身也不能保证断电后的落盘。不要把当前实现称为全程 exactly-once。

建议每个 unit 建 commit record：
1. intent.json：unit key、输入/request hash、attempt编号、目标输出和阶段状态；
2. write temp → flush + fsync(file) → os.replace → fsync(parent dir) 保存结果；
3. unit-result.json：输出清单和 hash，作为该 unit 的提交证据；
4. 更新 editor-state、metrics、completed-steps；这些是可核验/可重建的索引；
5. 成功返回。日志失败不能撤销已经持久化的结果。

崩溃在3之后、4之前：根据结果重建索引，不重新抓取/调模型。
崩溃在3之前：核验缓存/原始响应；只补当前缺失的本地计算。
完成标记存在但输出缺失/hash错：integrity_error，保留现场，不静默“当完成”。
不要一看到 completed-steps 就无条件 skip，也不要仅凭文件存在就信任它。

### 5.3 任务状态（提案，不是已实现字段）

prepared → awaiting_agent 或 ready_http → attempting → response_saved →
answer_validated → unit_committed；异常状态为 retryable / outcome_uncertain /
rejected_item / paused / blocked_integrity。
request_id 绑定输入，attempt_id 绑定实际一次远端调用；
不复用旧批次答卷，不修改任何已 pin 的 answer.json。
新修正单独任务/attempt，原始答卷保留以供质量对比。

### 5.4 HTTP 的关键崩溃窗口

当前 pipeline/agent_shadow_providers.py：
- HTTP 前保存 attempting；
- answer.json 写完、audit和complete写完之间可断；
- 检测到 attempting 会拒绝，并提示 fresh run，即使答案可能已保存；
- 对于 truly missing response，不能证明远端未执行。
这是首测前的重点修复，而不是删掉防重复调用检查。

实现方案：
1. 保存 raw-response.json（含request/attempt/config hash、响应、已知usage，不含key）。
2. 在网络返回后优先持久化 raw response，再导出 answer；
   audit统计由固定 attempt_id 幂等补记，未知usage明确 unknown。
3. 同目录恢复时先查 raw response / answer / unit result，并核对 attempt、revision、hash。
4. 有可信结果：补齐状态、验证并继续，不再 HTTP 调用。
5. 无可信结果：记 outcome_uncertain。若provider确有可验证的查询/幂等机制，才利用；
   不能假定 DeepSeek支持请求结果检索或幂等键。
6. 对 rewrite-batch 的不确定失联，禁止自动重新生成五篇。保持原run暂停待处理；
   如用户明确允许备用方案，只能从该次现存可恢复稿件保留好稿，
   对无法恢复的个别稿件建新的单篇任务，不伪称没有额外调用。
7. 非批量、无发布副作用的单篇任务，可提供受控授权重试：
   单 task 显式新attempt、累计预算不清零、默认最多一次；
   需要明确记录可能远端执行两次的成本风险，不能宣称 exactly-once。
8. JSON坏：现有native语法修正；词数/结构坏：单篇modifier/repair；
   已有整组五篇不得为修一篇而重新送DeepSeek。

### 5.5 一小时限制与续跑

当前 MAX_RUN_SECONDS=3600 用 started_unix 的 wall elapsed 包括 Bot等待/睡眠。
已暂停过一小时的run会被拒绝新task/HTTP，并要求fresh directory；与用户需求不一致。

建议将限额分开：
- 总调用/任务/正文抓取预算继续累积，恢复绝不清零；
- command active time（CPU/网络等活动）与 awaiting_agent / paused time 分开；
- 人工或已授权routine可显式恢复时间窗口，而不是换目录；
- 建议首次仍保留60分钟窗口、每次显式+60分钟、默认最多两次，
  具体数值由Claude审查后确认，不能当作已批准无限自动延期；
- 新 run date 不自动变今天。长时间暂停后，公开发布前重新核对本栏历史、
  来源状态和已发布revision；另存freshness-check，不篡改原始plan输入/已完成答卷；
- 超过24小时建议标记 stale_run 并由用户确认保留旧日期补跑还是开新轮。
  仍不删除旧轮或默默发过时新闻。

拟议接口（**目前不能运行**）：
`agent_shadow resume --run-dir R --extend-seconds 3600 --reason "..."`
`agent_shadow recover-task --run-dir R --request-id ID --reuse-response`
`agent_shadow retry-task --run-dir R --request-id ID --ack-uncertain --reason "..."`
后一个必须拒绝 rewrite-batch whole-group重发；不授权部署重试。
CLI只控制恢复，不让Bot手动编辑 audit/budget/hash 文件。

## 6. 异常分类与 Bot 行为

| 类型 | 行为 | 不允许 |
|---|---|---|
| 原生答卷未到 | exit2 + 相同request/read/write_to；等待答卷后step | 把exit2当失败不断空跑 |
| 单篇稿不合格 | 已有单次精修；仍差则备用，记录原因 | 整组重写、绕过安全检查 |
| 429 / 确认可重试服务错误 | 保存attempt结果，按限额/Retry-After延迟；具体provider语义审查 | 无限重试，预算清零 |
| HTTP read timeout / connection reset | outcome_uncertain，先找可信响应再续跑 | 默认当请求没执行 |
| 401/403 / 缺key | 同目录暂停，用户修身份后继续；不打印凭据 | 换成service-role绕过 |
| 候选原文/图下载失败 | 单候选记录失败，换备用；预算不重置 | 丢掉已抓到的正文或已过稿 |
| 锁占用 | 告知在跑，不启动第二实例 | 删除活锁 |
| 磁盘满 / 原子写失败 | 不宣称unit成功，保留已提交结果；报需处理 | 完成标记领先结果 |
| JSON/state/hash损坏 | blocked_integrity，保留原文件，报告 | 自动覆盖为[]或零历史 |
| HTTP调用数/抓取数耗尽 | 停该新增操作；已有合格稿仍在 | 换run绕过限额 |
| Git/Storage/DB结果不确定 | 只读查提交/对象hash/receipt后续缺项 | 重复commit、部署、入库或发信 |

保持现有 stdout 单行 JSON、退出0/1/2/3：
0完成单元、2原生交接或答卷待修、3已完成、1工具/完整性/权限错误。
拟新增 error_code、retryable、outcome_uncertain、resume_command、request_id、
retry_after_seconds；通过结构字段区分“可恢复暂停”与“永久失败”。
不要突然新增未写runbook的退出码。让Bot在已授权范围内按明确next恢复，
不要求Bot自行改代码/阈值/身份或替换生产配置。

异常重试逻辑放 Python；Grok只做内容判断及允许的修稿。
恢复输出必须是 .venv/bin/python 命令（不能依赖VM系统python包）。

## 7. 具体代码修改计划（审查后实施）

| 文件 | 改动 | 优先级 |
|---|---|---|
| pipeline/agent_shadow_providers.py | attempting+已落盘response重建；attempt累计；结构化不确定错误；wall窗口续跑 | 首测必须 |
| pipeline/ai_providers/transport.py | 新状态持久化按需fsync、响应校验/持久化边界；保持生产适配路径不变 | 首测必须 |
| pipeline/agent_shadow.py | resume/recover接口、status显示当前task/错误/可继续命令；unit commit核对；日志错误隔离 | 首测必须 |
| pipeline/agent_shadow_batch.py | 五篇答卷与selection之间被杀后复用；单ID修正被杀后复用；不重写settled栏目 | 首测必须 |
| pipeline/agent_shadow_editor.py / autonomous.py | 只核对必要的输出依赖；抓取/尝试计数在崩溃时不回滚 | 首测必须 |
| agent/skills/kidsnews-shadow/SKILL.md | exit语义、等待/同目录恢复/禁止删状态/禁整组重发 | 首测必须 |
| docs/KIDSNEWS-BATCH-AND-ZIP-RUNBOOK.md / BOT.md | 新命令必须实现后才升级为可执行，修改旧fresh run描述 | 首测必须 |
| pipeline/publication_bundle.py | upload/verify超时先GET核hash/ready；409必须同包比较 | 生产前必须 |
| supabase/functions/finalize-news-publication/* | 分阶段失败恢复、扫描积压、公示与DB竞态复核 | 生产前必须 |

共享 transport 可能影响生产：优先用新的shadow wrapper，不改变现有生产HTTP重试行为；
若改纯持久化函数，增加生产兼容回归。不要为了resume删掉安全预算/答案防篡改。
本表说明要检查和改动的位置，不表示所有行都有已证实bug。

## 8. ZIP、数据库和发布恢复

Bot只上传结构化成品，不能在ZIP放任意SQL。
每包ID/ZIP hash不可变；新内容必须新package_id。
数据库写入只由定时消费者按固定校验和固定事务进行；
专用uploader仅可insert/select私有ZIP/ready，不可写done或业务表。

保留原有GitHub Action，不把它改成新Python流水线。
Bot stage解包内容到新目录，网站的Git交接仍遵循PR/明确生产授权。
同一ZIP可交两个位置，ready只在公开站点逐文件hash核验通过后上传。
网站现有登录/归档shell不能被影子shell替换。
ZIP/Storage/DB/网站没有全局事务，必须允许短暂不一致，并明确当前进度。

发布恢复检查顺序：
1. 查Git远端SHA/PR和公开manifest/payload hash，不重复部署。
2. 上传失联：查私有ZIP字节hash，匹配则续ready，不无条件overwrite。
3. ready失联：查同包ready；不允许Bot写服务端done。
4. worker取得lease，核验公开内容和新旧revision。
5. DB receipt存在：不再插入/重复更新source cadence，补未完成归档。
6. archive-index读取失败：暂停，不初始化空索引丢旧历史。
7. done只在必要阶段都成功后写；DB先提交但index失败不声称全完成。
8. 正常生产writer不参加新worker锁，仍可能覆盖站点/latest；
   上线前需明确单writer窗口/授权切换方案，不因“06点多才跑”推定没有竞态。

新migration/Edge/cron/uploader权限均尚未在生产启用。
隔离Supabase测试：权限、真实schema、Storage上传、重复包、失败恢复、
旧版保护、website archive reader兼容先通过，再做授权生产试用。
儿童/家长业务表、邮箱及Auth不作为新ZIP合同数据。

## 9. 回归与故障注入验收

新修复各先写失败测试，修复后通过；mock模型避免真实费用。
正常190项保持绿，并在Python3.10下跑。测试数量不能替代实际注入。

| 建议测试名（待新增） | 注入与断言 |
|---|---|
| test_resume_after_saved_answer_before_http_complete | answer可信落盘、complete缺失；恢复HTTP次数不增加 |
| test_resume_after_raw_response_before_answer | raw在、answer未在；生成answer并继续，usage只补一次 |
| test_uncertain_missing_response_keeps_run | 响应无证据；同目录pause，不清候选/初稿，不wholebatch retry |
| test_resume_after_wall_deadline_without_resetting_budget | 模拟暂停2小时，显式续窗口；原task/call/fetch计数保留 |
| test_resume_window_is_bounded_and_stale_date_checked | 超最大延期/日期过旧，不默默发旧稿 |
| test_sigkill_at_every_unit_commit_boundary | subprocess注入kill，结果提交前/后及索引前/后；不重复外部调用 |
| test_batch_interrupt_between_writer_and_selection | 五篇已落盘、Grok未答；仍用同五篇，不第二次DS写批次 |
| test_single_repair_interrupt_preserves_other_four | 修一篇中断；其他4篇hash相同 |
| test_fun_refill_crash_does_not_repick_news_science | 已满足两栏抓取数、selection请求hash、成品hash不变 |
| test_disk_full_never_commits_completion | 保存失败无假完成，之前结果仍可读取 |
| test_logging_failure_does_not_repeat_committed_unit | steps.jsonl写失败，不触发模型重调 |
| test_corrupted_state_is_not_silently_reset | 损坏state无空列表替代，明确完整性错误 |
| test_recovery_cli_single_json_and_exit_codes | 真CLI子进程exit1/2/0/3、stdout单行、.venv命令 |
| test_http_uncertain_does_not_duplicate_upload | 包上传/ready超时与409先核hash，不重复写 |
| test_db_receipt_then_archive_index_failure | DB1次、同包恢复补index、来源轮换不二次累加 |

测试两个仓库导出字节一致；UPSTREAM记录新共享SHA。
实际VM新目录一次完整测试，随后在同一run中故意中断一个已定义安全点并恢复；
总数、所有稿件ID/hash、累计调用、原文抓取次数与无中断基线比较。
不要在真实生产写入时随意kill来验证，先用隔离环境/本地fake。
报告active/network/native-wait/paused分别耗时，另列wall elapsed；未知Grok配额记未知。

## 10. 备份与文件保留

已生成本机应用逻辑备份：
/Users/jiong/.local/share/kidsnews-backups/20261001T030535Z-lfknsvavhiqrsasdfyrs/manifest.json 。
Supabase ref lfknsvavhiqrsasdfyrs 是共享数据库；public 96表、19,250行，
约119MB，含KidsNews stories414/source configs40。仅本机受限权限，不入Git/ZIP/Bot。

备份JSON回读、行数、SHA256通过，**未做restore演练**；
不含Auth、Storage文件字节、其他internal schema或完整DB角色；
结构metadata不是完整pg_dump DDL，不能声称可一键整库恢复。
云端backups接口当时返回空列表；正式schema变更前需在隔离库演练
目标KidsNews表的恢复，必要时另做provider认可的完整备份。
备份内容可能包含其他项目/私有字段，绝不发给Claude/Bot聊天、Git或公开网站。

用户要求这几天保留：registry/input、bodies、candidate-images、batch答卷、
modifier前后稿、details、review结果、state、metrics、provider-audit、日志、site与ZIP。
未来cleanup另立spec：先保留规则/完结状态/恢复引用检查/dry-run，再执行。
不能清正在跑/暂停/不确定发布中的目录；未恢复完成的run默认不清。
本草案不清理任何本地缓存或中间文件。

## 11. 执行顺序与进入 Bot 的门槛

A. Claude只读审查本草案+基线代码，列首测阻塞、生产阻塞和可后做项。
B. 本地修首测阻塞，先红后绿测试；更新runbook明确已实现CLI。
C. 源feature提交/PR更新、Atlas JSON；导出Bot、3.10复测、UPSTREAM、Bot提交/PR更新。
D. 报告API成功只表示本机Brain；Brain GitHub/Atlas网站需分别核验/待同步。
E. 用户确认后，在VM用新测试run开始；发生中断继续同一个run。
F. Bot仅按代码stdout/task答卷运行，不改代码、预算、阈值、已通过答卷；
   初稿格式修正/单篇modifier属于允许内容工作，不是无限自治改系统。
G. 真实九篇/成本/时间/断点通过后，再审查隔离Supabase部署。
H. 云端权限/事务/归档/重试/备份恢复通过，再另行生产发布授权。
不将 A→D 完成说成 E→H 已完成，也不把“pipeline成功”说成收件箱收到邮件。

当前已存在的安全状态命令（可读，不调用模型）：
`.venv/bin/python -m pipeline.agent_shadow status --run-dir work/D/batch-1`
普通未超时恢复的现有命令：
`.venv/bin/python -m pipeline.agent_shadow step --run-dir work/D/batch-1`
超时/不确定问题修好前，不把拟议resume/recover命令给Bot直接运行。

## 12. 可复制给 Claude 的只读审查提示

请先读本文件及两个仓库AGENTS.md，再核对本文第2节基线；
用实际git status确认没有其他会话的改动，不覆盖未提交文件。
这里只读审查，不修改、不commit/push、不merge、不调用真实模型、
数据库写、部署、邮件或Bot消息。不读取.env、密码或备份数据内容。

重点：代码已实现与文档目标是否分明；同目录resume的所有崩溃窗口；
attempting但answer/raw已落盘的恢复；无响应不能证明未执行；
禁止整组5篇再生成与预算累计；一小时wall deadline改造；
结果与完成标记的多文件事务；日志失败与网络重复调用；
三栏补稿隔离、图片哈希；ZIP上传/DBreceipt/归档恢复；
生产路径不变、旧writer竞态，以及备份不可声称整库可恢复。

可运行现有离线测试，使用专用Python3.10。不得安装/升级全局环境。
对每条发现给出 severity、文件/行号、具体复现、影响、修法和失败回归建议。
分别给出：
1. 首次真实Bot影子运行的阻塞项；
2. 不阻塞影子但阻塞生产部署的项；
3. 可后续优化；
4. 本spec的矛盾/遗漏与应修订规则。
不要仅凭190/7测试数字认定已满足新异常恢复要求。
审查后先交人确认，再由本地实现者修代码；不是让Bot自行修基础设施。
# 2026-09-30 审查实施增补（优先于下方原始设计的冲突条款）

本次按同名 REVIEW 的 B1–B7/S1/S2/S4/S7实施影子恢复，不启用生产部署。
一小时wall-clock限制取消；持久预算保留。超过24小时需step --confirm-stale及新只读registry，
先重核七天历史，日期不变。HTTP答卷是原子提交记录，不再用complete状态作二次提交。
已知未执行失败可预算内重试；uncertain不自动HTTP重发，显式native兜底才交Agent。
native兜底原生批量四稿(3+1)，request_id/校验保持，隐藏HTTP max_tokens；连续两轮熔断。
每栏正文抓取12独立计数；只为有未尝试改善候选的重要News/第二Science出版方补稿。
具体命令、状态/诚实标记见KIDSNEWS-BATCH-AND-ZIP-RUNBOOK.md及运行SKILL。
P1–P5生产问题仍未修，本增补不是生产上线许可。下方原Spec保留为设计历史，不覆盖本增补。

## 2026-10-01 Grok后续修复增补

1. 传输兜底先进入fallback_pending，原子归档并移除旧HTTP答卷，再写原生请求及
   fallback_native。恢复兼容旧版本在fallback_native状态遗留HTTP答卷的窗口，
   必须重新交接原生答卷，不允许通过更改revision/来源标签把旧结果当新结果。
2. 原生批量最多四篇(3+1)：可见任务追加覆盖五篇的规则，Python答卷硬校验也约束四篇。
   HTTP正常批量仍选五篇；兜底request_id仍复制原值，原任务身份不重算。
3. 超24小时历史复核使用初始候选+当前自主目录发现候选，按最终分栏查本栏历史；
   归档字段与prepare共用规则，兼容archived/is_archived。冻结目标日期仍排除，
   不改用户允许同日覆盖的规则；已通过但被新历史判重复的稿仍移除。
4. 每栏12次正文抓取只限制新增下载。已缓存合格原文仍可入池、沿目录扩展和局部补稿；
   不能因目录前方一个未缓存项就停止读取后方缓存。不得重置计数、重复写已消费初稿。

测试与实施状态见KIDSNEWS-GROK-FOLLOWUP-2026-10-01.md；8项新回归先红后绿，
Python3.10相关227项通过。Grok提出的累计revision重试限制保留为可选策略，
不禁止修好身份后同目录恢复；P1–P5继续延期，生产路径、图片政策及发布授权均不变。
