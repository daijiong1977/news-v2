# Kids News 两阶段迁移：网站先行 Spec

日期：2026-10-01。状态：**待 Cloud 审核，非执行发布授权**。
项目：kids-news-website。第一阶段不要求实现数据库/archive 的全链路回滚。
本文和配套 RUNBOOK 是本次最新合同；旧 SAFE-TRANSITION 中关于独立测试域名、
先同步数据库再完成试用的方案保留作历史/第二阶段参考，不作为第一阶段必做项。

## 1. 目标、仓库与基线

目标：先用正式网站模板展示混合 Bot 的九篇新稿，通过旧同步 Action 部署；
不满意时恢复旧成品，不重新调用模型。稳定几天后再单独评审后台同步。

| 仓库 | 本地 / VM | 分支与职责 |
|---|---|---|
| daijiong1977/news-v2 | /Users/jiong/myprojects/news-v2-agent-provider | codex/agent-provider-boundary，先改共享源码；PR #86 |
| daijiong1977/grokbot-kidsnews | /Users/jiong/myprojects/grokbot/grokbot-kidsnews；VM /workspace/kidsnews-shadow | codex/stepwise-full-shadow，最后导出运行快照；PR #1；main 仍不是当前运行入口 |
| daijiong1977/kidsnews-v2 | /Users/jiong/myprojects/kidsnews-v2 | 正式网站 main，原 Action 管理 site/；本次不改其工作流 |

审查前代码基线：共享 72b38b28b219d1ecc3c4e7cf0ad99665f7c4d40a；
Bot 8928c0a94d08b86b425c52994917b1c3ad733a3a。后续文档提交并不表示新增发布功能已实现。
正式域名 kidsnews.21mins.com / news.6ray.com。news.21mins.com 是历史测试域名提议，
本方案不要求创建它，也未核验其 DNS / 归属 / 绑定。

## 2. 阶段边界（强制）

### 第一阶段允许

- 只读来源、历史；调用已配置 DeepSeek 和原生 Grok；本地生成、校验和预览。
- 明确批准后，将正式 reader ZIP 写入 redesign-daily-content/latest.zip；
  同步写入匹配的 latest-manifest.json；恢复时也只恢复这两个对象。
- 发送 kidsnews-v2 的 news-v2-uploaded repository_dispatch，沿用既有 Action。
- 保存独立备份、私有运行日志和可恢复的有效发布历史账本。

### 第一阶段禁止

- 发布入库、修改 redesign_stories / redesign_search_index / redesign_source_configs /
  redesign_runs 或账号/阅读/家长数据。既有网站自身正常用户操作不在此禁令范围。
- 改写 YYYY-MM-DD.zip、YYYY-MM-DD-manifest.json、YYYY-MM-DD/ 日期目录、
  archive-index.json；不运行归档保留/删除。不因为 bucket 名含 archive 就误判 latest 禁写。
- 调用 finalize-news-publication，上传 pending ZIP/ready 标记，启用新消费者/迁移/cron。
- 改现有网站 Action、DNS、Vercel 配置；Bot 直接提交网站 main；运行生产 full_round。
- 自动发送额外邮件，删除缓存/答卷，或者擅自合并 PR、改代码/阈值。

第一阶段是网站内容试用，**不是 DB/archive 一致性切换完成**。历史页和搜索仍可能
展示旧内容；同日 slot ID 对应不同稿件的阅读记录、搜索跳转和自动修复风险必须抽查。
上线前若发现会损坏用户功能，停在预览，不擅自以 DB 写入补救。

## 3. 内容链路与职责

1. Python 读取 registry；history 键必须存在且三栏不能全零。取各栏 D-7 <= date < D，
   不跨栏，目标日同日重跑排除。有效网站发布账本的合并见第 8 节。
2. Python 采集 RSS 元数据、清理 URL/完全重复标题；Grok 一次 plan 按分栏、
   同事件历史、重要性/趣味性形成每栏最多 30 项备用目录，不先读全部正文。
3. Python 按排名读取最多八篇合格原文，同时抓来源图、解码、检查尺寸/格式/hash；
   每栏正文抓取预算 12 次（失败计入），图片用现有来源图机械检查，不额外视觉任务。
4. DeepSeek 每栏一次八选五，并写 easy/middle/中文正文及选题理由；不另加预选调用。
5. Grok 每栏五选三，另两篇备用。第一篇 News 优先重要性；Science 优先学科多样性。
6. Grok 修所选单篇并自检，定点修改归因/引语/限定语/中立/儿童表达，仍不合格才换
   备用。只缺一栏就补那一栏，不重写五篇、不重选已通过的其他栏目。
7. 冻结最终标题/正文/中文；Grok 每篇一次生成 easy/middle 详情并自检，无额外
   review-details 任务。背景/观点只能有据，可为空；不得发明头衔、年份、数字。
8. Python 校验结构、过滤正文不含的关键词、确定性洗牌和最长答案告警，保留有限
   格式修复机制。无第三模型审核，不声称“独立详情审核”。
9. Python 打正式网站包、检查所有引用、预览；先停止等待包级发布批准。

正常无失败轮：3 次 DeepSeek 正文调用；原生 plan 1 / select 3 / modifier 9 / details 9，
共 24 个判断任务。重试、补稿另计。Grok 账单无法从日志取得就写未知，不保证 3% 周配额。

### 选文合同

- News：合格的重要新闻先选，政治/战争/死亡可解释；删血腥、煽动/反复恐惧，不因
  成人议题整类剔除。争议有据归因，不捏造“双方观点”来假平衡。无重要稿明确告警。
- News 接受两家合格出版方；Science 至少两家；Fun 当前仍三家。质量优先，不编稿凑数。
- 公共事务 Tech/AI 和政府动物外交留 News；趣味科技和非科研动物趣事入 Fun；
  动物生物学及 physics / chemistry_materials / astronomy / biology 留 Science。
- Science 优先不同学科，再兼顾独立出版方；不能把 ScienceDaily 的不同 feed 当不同出版方。
- Fun 优先真正趣味及游泳/网球；同质量合格时，知名明星的当前比赛、复出、纪录优先
  一般体育/情感退役回顾。不强凑明星、排除大学招募/无趣讣闻/消费导流。
- 备用换稿保留安全/历史门禁，不新增同日补稿模型去重轮；耗尽就保留现场告警。
  网站正式试用仅允许完整 3+3+3 包，少稿不上传、不拿昨日成品自动补齐。
- 具体原文/成稿字数以 agent_shadow_lengths.py + wordcount_policy.py 为准，不能沿用
  旧文档的 Fun 250 下限；当前影子 Fun 原文 180–1200，Science 原文 350–1500。

## 4. 正式包与 manifest 合同

ZIP 根目录必须直接包含 index.html、正式 JSX/JS/CSS/字体/组件，以及：

```text
payloads/articles_{news|science|fun}_{easy|middle|cn}.json  # 9 个列表
article_payloads/payload_<story_id>/{easy|middle}.json     # 18 个详情
article_images/<image>.webp                              # 每篇可解析图片
```

不增加 site/ 或 website/ 外层目录。ID 为 D-category-slot，与列表/详情/图片一致；
正文在详情 summary，保留 questions/options/correct_answer 等现有 reader 字段。
固定经过验证的正式 reader commit + shell 文件 hash 清单；包含 index.html 引用的
.jsx 和 components 子目录。修复 publication_bundle.py 遗漏 .jsx 后还需浏览器验收，
不能仅改白名单就称正式兼容。使用新目录，不修改正式 checkout 或旧 ZIP。

区分两个包：内部 publication.zip（records/usage/影子审计）与实际公开 reader ZIP。
公开包只含正式 shell 和 reader 所需数据，不泄露 tasks、答卷、私有审核、内部
publication-records/source-usage、影子 app、.env。内部原 ZIP 保留，公开包另取名称。

latest-manifest.json 沿用旧消费者字段：version、packed_at、git_sha、zip_bytes、
zip_sha256、story_count、stories。由实际公开 ZIP 生成；git_sha 的仓库归属/模板 SHA
另明确记录，不能把内部 publication-manifest 当作旧 manifest。模板与内容 hash 分开记。
总包大小/路径穿越/重复 ZIP entry/symlink/图片解码/文件引用均要机械验证。

## 5. 现有部署机制（已核实）

kidsnews-v2/.github/workflows/sync-from-supabase.yml：

```text
repository_dispatch(news-v2-uploaded) / workflow_dispatch / 每两小时 UTC :15
→ GET redesign-daily-content/latest.zip（带 cache-busting）
→ 清空 site/ 后解包 → commit/push → 既有网站部署
```

上传不是 Storage 自动通知；只推 Git 里的 ZIP 也不会被这个 Action 读取。
Action 不读 manifest，也不核验业务完整性，因此这些门禁须在上传前的 Bot 脚本完成。
同步 Action 成功不等于公开站正确：须读回部署后的列表/详情/图片逐文件比对。

## 6. 发布与恢复状态（待实现的网站专用适配器）

运行目录保存 release.json：日期、package/ZIP hash、source commit、template commit、
备份 ZIP/manifest hash、批准的精确包、各阶段时间、Action run/站点验证、失败原因。
备份保存在 /workspace 下持久目录并另存可恢复副本（位置必须操作前确认），不能
只留 /tmp；备份可包含公开网站成品，不含账号/儿童私有数据。

阶段：built → checked → approved → backed_up → upload_attempted → uploaded_verified
→ dispatch_attempted → sync_observed → public_verified；rollback 使用独立操作 ID。
状态原子写、互斥、恢复按已完成步骤继续，不重新生成正文。批准绑定日期+hash，
包改变批准失效。批准前最新远端 hash 若变化必须重新确认备份和目标。

上传 ZIP/manifest 为两个对象，**不是原子事务**；定时 Action 可在上传期间启动。
必须处理此窗口/缓存和失败后不一致：不提前宣布成功；先验证 ZIP，再写匹配 manifest，
读回双 hash；失败可从备份恢复并验证。Cloud 审查需决定可接受的有限窗口/操作窗口策略。
超时先查远端，已匹配则继续，不盲重发；相同包恢复是幂等操作。

旧 Daily、republish-bundle、quality/autofix 都可能写 latest；本机锁不能阻止它们。
首试只在明确的无冲突窗口、确认无在途 writer 时执行；保持早上旧流程作为备用。
不自动关闭旧调度。如无法证明试用/回滚期间没有竞争，停止等待人工安排。
新后台消费者必须保持停用且无 pending 投递。

## 7. 网站回滚（第一阶段）

1. 停止本次后续发布步骤，确认无竞争 writer，选择本次 backed_up 对应旧包。
2. 验证备份 ZIP/manifest hash，拒绝损坏或不匹配的备份。
3. 恢复 latest.zip 和 latest-manifest.json，读回确认，发送同一同步事件。
4. 观察对应 Action/部署并公开比对旧包，标 rollback_public_verified。
5. 恢复有效发布账本指针；保留新旧包与错误现场，不删除数据库/archive/个人数据。

旧 pack_and_upload.restore_latest_from + republish-bundle.restore_from_date 可恢复日期包，
但现实现允许缺 manifest、跳过验证，不能当作新安全门禁已实现。日期包不再是
不可变保证（旧上传 upsert=true）。本阶段不改日期包，独立备份仍是首要退路。
不从 DB 重新生成，不绕过新 worker 的 revision 检查（本阶段根本不启用 worker）。

## 8. 几天试用的历史/来源记录（待实现）

DB 未入库不能让 Bot 忘记已发稿。维护可恢复的网站有效发布账本：按日期/栏目
替换该日有效发布集合，而不是将旧 DB 与 Bot 同日稿重复累加；未批准/失败/仅影子
产物不进入。仅 public_verified 后生效，回滚恢复旧集合。持久保存并备份，不能
靠日志里的 done 或曾生成过就算已发布。

下一轮 registry = DB 本栏目七日历史 + 账本中覆盖的有效日集合；仍排除目标日 D。
原 URL/source title/event/topic 信息须足够原有判重用。来源实际使用记录仅本地
覆盖有效 last-use，不更新 Supabase。多 VM/目录并行时必须同一账本所有者。
旧生产流水线暂不读取该账本，故早上旧稿可能重复 Bot 昨日内容；这是过渡限制，
应人工观察，不误称全系统历史已同步。搜索/历史 archive 也仍旧，不伪造同步状态。

## 9. 权限与执行身份

VM DeepSeek key 只在 .env；Storage latest 写权限与 GitHub dispatch 权限需要实际
核验。现仅覆盖 grokbot-* 的 PAT 不代表可触发 kidsnews-v2。可复用经批准的发布
执行身份/连接器，不能为方便泄露服务密钥、让浏览器持有它、或打印全部环境变量。
实现需明确“由谁上传/由谁发送事件”；未就绪则停在 ZIP，不让 Bot 自行扩大权限。
更新代码走 PR，正式包批准与代码合并批准分开；不把 spec 认可当发布授权。

## 10. Spec ↔ Code 状态矩阵

| 要求 | 当前文件/证据 | 状态与差距 |
|---|---|---|
| 8→5→3、单篇修稿/备用 | agent_shadow.py、agent_shadow_batch.py、agent_shadow_editor.py | 已有 opt-in 实现及离线测试；新轮实际质量待测 |
| 原生详情一次生成自检 | agent_shadow_details.py、config/shadow-batch-grok-details.json | 已实现；无额外 review-details；Python 校验非独立审稿 |
| 来源图机械检查、长度 | agent_shadow_photos.py、agent_shadow_lengths.py | 已实现；不是视觉批准 |
| 同目录恢复/持久预算 | agent_shadow.py、agent_shadow_providers.py、ai_providers/transport.py | 已有回归；不得删状态重置预算 |
| 正式模板复制 | publication_bundle.py build(shell=...) | 部分入口已有，但漏 .jsx；阻塞正式发布 |
| 公开 reader ZIP / 旧 manifest 生成 | publication_bundle.py；旧 pack_and_upload.py 参考 | 尚无本阶段专用转换器，内部包不能直接顶替 |
| latest-only 上传与备份/批准/恢复状态 | 当前 publication_bundle upload | **未实现**；现 upload 是 pending handoff，不可调用 |
| 旧同步触发和日期恢复 | kidsnews-v2 sync-from-supabase.yml；news-v2 republish-bundle.yml | main 机制已读；实际权限/安全门禁/恢复演练待验证 |
| 公开文件匹配 | publication_bundle.py verify_site | 有基础函数；正式包/域名目标与完整 reader 验收待接入 |
| 有效网站历史与来源 overlay | registry_snapshot.py、publication_history.py 参考 | **未实现**，现 registry 仍只依赖传入历史 |
| 旧新 writer 协调 | 旧 Daily/republish/quality 工作流 | 未实现跨 writer 锁；需人工确认运行窗口，不能声称原子 |
| DB/archive 同步、P1–P5 | finalize-news-publication、迁移、旧 REVIEW | 第二阶段，暂不启用、不修成第一阶段依赖 |

路径默认相对于共享 repo，pipeline/ 前缀略写。原影子 237 项通过记录不证明上述
未实现发布功能通过。此次文档修订不改 runtime 行为。

## 11. 验收清单与第二阶段

第一阶段新增测试至少覆盖：正式 JSX 依赖/字段/图片/缺栏拒发；公开包无私有材料；
latest-only 写入 allowlist（断言从不写日期对象/DB/pending）；独立备份完整；批准后
包/hash 改变拒绝；上传/dispatch 超时查状态不重做；恢复重复执行及中断续；竞争
writer 停止；next-day 历史 overlay/回滚恢复；无需模型的部署与恢复。
离线 fake Storage/dispatch 测試 + 正式模板浏览器预览 + 明确批准的一次真实发布/
网站恢复演练各自报告，不混称同一通过。Python 3.10 为 VM 测试环境。

第二阶段另开 spec/review：live schema 与约束、归档/搜索/来源轮换、ZIP consumer
P1–P5、后台定向恢复/幂等/单 writer。质量稳定只触发评审，不自动上线后台。
运行细则与 Cloud 审查消息见 KIDSNEWS-WEBSITE-ONLY-RUNBOOK-2026-10-01.md。
