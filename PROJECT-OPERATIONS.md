# Kids News 项目地图与交接（2026-09-27）

本文按本次核对的 Git 远端、工作树、工作流和代码记录**当前结构**。历史设计见 `docs/PROJECT-OVERVIEW.md`；其中仍有“kidsnews-v2 尚未创建”“30 分钟轮询”等过期描述，不能用来判断现在是否上线。运行数、来源表和分支会变化；下表的 SHA/数量是核对时的快照，不是永久配置。

## 1. 仓库、目录和同步链

| 位置 | 职责 | 本次核对 |
| --- | --- | --- |
| [daijiong1977/news-v2](https://github.com/daijiong1977/news-v2) | **生产内容流水线源码**：RSS/HTML 采集、JEV 与 DeepSeek 选稿、改写、安全复核、Supabase 存储、网站模板、后台和质量邮件 | 远端 `main` 为 `e44cdc9`；本项目的 PR 应以它为基准 |
| `/Users/jiong/myprojects/news-v2` | 同一仓库的本机主 checkout | 当时在 `codex/science-fun-groups-routing`，不是最新 `main`；另有未跟踪文件。不要在此目录直接推断生产状态或覆盖文件 |
| `/Users/jiong/myprojects/news-v2-fun-source-pool` | 同一仓库的独立 Git worktree | 当前 `codex/project-atlas-handoff`、[PR #74](https://github.com/daijiong1977/news-v2/pull/74)；`supabase/.temp/` 是已有未跟踪目录，不纳入交接提交 |
| [daijiong1977/kidsnews-v2](https://github.com/daijiong1977/kidsnews-v2) | **部署仓库**：同步生成的 `site/`，由 Vercel 发布；不是第二套选稿算法 | 远端只有 `main`，本次核对为 `0234e11`（2026-09-27 15:31 UTC 内容同步） |
| `/Users/jiong/myprojects/kidsnews-v2` | 部署仓库的本机 checkout | 本地 `main` 比远端 `main` 落后 248 个提交，且 `.gitignore`、`vercel.json` 有未提交修改；先查远端，不要在该目录直接 pull/覆盖 |
| Supabase `redesign_source_configs` | 实际来源表：启停、栏目、优先级、cadence、星期和下次抓取时间 | 数据库配置，不在 Git 中；旧文档中的来源数量只是某次运行快照 |
| Supabase Storage `redesign-daily-content` | 每日归档和供部署读取的 `latest.zip` | `pipeline/pack_and_upload.py` 负责验证、上传；成功上传不等于读者端已更新 |

当前发布链：`news-v2 main` 的 `.github/workflows/daily-pipeline.yml` 定时或手动运行 `pipeline/full_round.py` → 写 Supabase 故事与 `latest.zip` → GitHub `repository_dispatch` 触发 `kidsnews-v2` 的 `.github/workflows/sync-from-supabase.yml`（每两小时定时兜底）→ 下载并替换部署仓的 `site/`、有变化才 commit/push → Vercel 发布。流水线会尝试核对同步提交；仍须分别检查 Action 结果、部署仓新提交和公开页面。2026-09-27 两个公开入口 `https://kidsnews.21mins.com/`、`https://news.6ray.com/` 均返回 HTTP 200；这仅证明入口可访问，不证明某次新内容已经发布。

当前 YAML 中 Daily pipeline 的定时触发为每天 **07:00 UTC**（纽约夏令时 03:00；冬令时不是同一个本地钟点），管理员配置还可能停用当次定时或改变运行 variant；手动运行不受这个停用门槛约束。Quality digest 由 Daily 完成事件触发，目标是在原流水线触发后约 92 分钟检查；Parent digest 每天 10:00 UTC 触发，函数再决定哪些家长到期。同步仓的兜底 cron 为每两小时的第 15 分。旧注释提到“30 分钟轮询”“固定睡 1 小时”等均不应盖过当前 YAML 的实际配置。

本机 `website/` 是打包素材与模板；部署仓远端 `site/` 是同步结果，不能把两者当成互相独立、需要手工双向合并的源码。`newdesign/` 和旧版设计说明是历史参考。旧 `news`、`kidsnews`、`kidsnews-v2-snapshot` 不在本次核对的上述工作目录中；不要仅凭名字推断它们仍参与生产。

## 2. 分支与 PR：哪些才是当前工作

| 分支 / 工作树 | 用途与状态 |
| --- | --- |
| `news-v2` 的 `origin/main` | 当前生产流水线代码；更改先走功能分支、测试、PR，再由获授权者合并。2026-09-27 核对 SHA `e44cdc9`，已包含新闻质量和邮件安全的已合并修复 |
| `news-v2` 的 `codex/project-atlas-handoff` | 当前文档和 `.project-atlas/project-status.json` 交接工作；唯一查到的开放 PR 是 #74，未合并时不代表生产代码或生产文档已更新 |
| `kidsnews-v2` 的 `origin/main` | 部署仓的同步分支；远端只查到这一条分支，暂无开放 PR；同步 bot 的内容提交与 `news-v2` 的代码提交是不同 SHA |
| 本机其他 `news-v2` checkout：`codex/science-fun-groups-routing`、`codex/cbc-news-source`、`codex/quality-digest-rca` | 历史/专项工作树。后两者的 HEAD 已是当前 `origin/main` 的祖先；`science-fun-groups-routing` 的 HEAD 不是祖先、也没有开放 PR。不能把本机分支名或“未合并祖先”直接解释为正在部署的功能 |

`news-v2` 远端仍保留许多旧专题分支（本次列出 60 个远端引用），**分支存在、未被 Git 识别为 `main` 的祖先，都不等于正在开发或等待合并**。本次通过 GitHub PR 列表确认只有 #74 开放；每次交接先重查 `git fetch origin`、`git branch -r`、`gh pr list --state open` 和 `git worktree list`。避免在其他会话的脏工作树上提交或清理。不要直接 push 生产 `main`。

## 3. 当前算法：从来源到发布

以下是 `news-v2` 当前代码的职责边界，容量是上限/偏好，不是每日保证值。

| 层次 | 当前规则与调参入口 |
| --- | --- |
| 来源轮换 | `pipeline/db_config.py::load_sources` 从 `redesign_source_configs` 选启用且当天可用的来源：先到期、主来源优先，再按时间、优先级、cadence、最近使用排序；不够时可用未到期来源补齐。`pipeline/full_round.py` 首轮最多 News/Science 各 8 个 feed、Fun 10 个；News 每 feed 最多 12 条，其他每 feed 最多 4 条 |
| 便宜的初筛 | 先做本栏目过去 7 天的 URL/标题历史过滤及禁词检查，JEV 对标题/摘要做购物、严重伤害、英国本地事务、大学招募等早筛；失败/不确定有明确回退，不能把 JEV 预筛当作儿童全文审核。`pipeline/jev_prefilter.py` 的 8 篇是软性保留底线，明确招募排除不因此恢复 |
| 正文与路由 | 抓原文、按 350–1200 词探测并缓存；`editorial_routing.py` 只有栏目置信度 ≥0.90 才搬栏。公共事务 Tech/AI 和重大政治/外交在 News，生物学研究在 Science，趣味科技/动物趣事在 Fun；规则见 `docs/editorial-category-routing.md` |
| JEV 评分与题材 | `jev_rank.py` 按栏目适配、编辑价值及 News 重要性/Science 学习价值/Fun 趣味性评分；Fun 中游泳、网球重大赛事是软性加分。`news_topics.py` 标注题材；先剔除同事件，再用 `for_curator` 在完整合格候选目录中软换位，提高送审题材差异。News/Science 最多送主编 6 篇、Fun 最多 7 篇；主编排序最多 5 篇，每栏首批改写最多 4 篇。目录**不是旧版固定前 10 篇** |
| 发布历史与补稿 | `publication_history.py` 对每栏分别检查本栏目此前 7 天（不含本编辑日）已发布事件；先判规范化 URL/完全相同标题，再以 JEV 判断可能的同事件，不靠两个标题共同词门槛。补稿优先未占用题材的合格候选，再试其他候选或同日 feed 深挖；每篇仍须过历史、正文、字数、独立全文安全审核。目录耗尽时可发少于 3 篇新稿，不拿昨日成品充数；同日重跑是覆盖当天，不检查被覆盖的当日稿 |
| 最终组合与质量 | `editorial_policy.py` 在安全合格稿里联合优先 News 重要稿、Science 至少两家出版方、题材/来源多样性；ScienceDaily 多个 feed 只算一家出版方。`quality_digest.py` 的来源提醒阈值是 News/Fun 3 家 source、Science 2 家 source，**source 名与 publisher 身份不可混用**。每篇 easy/middle 改写后的正文都须经过独立儿童安全复核；战争/死亡的中性事实可保留，血腥与恐惧渲染不行 |
| 交付 | `full_round.py` 做 enrich、持久化与打包；`pack_and_upload.py` 验证并上传。`.github/workflows/quality-digest.yml` 后续检查质量，`pipeline-watchdog.yml` 管失败，`parent-digest.yml` 调父母摘要；工作流成功、邮件送达、网站内容更新是三个不同判断 |

## 4. 这轮踩过的坑、验证边界和可复用经验

1. **同题材不是同事件；同事件也可能换标题/换媒体。** 美国东北暴雨跨 BBC/CBC 漏过旧“两共同词”门槛。现在七天历史是**同栏目**比较，题材只是多样性软偏好；Fat Bear Week 这类跨过七天的长活动仍可能复现，目前仅记录潜在改进，不擅自扩大窗口。详见 `docs/bugs/2026-09-27-storm-repeat-history-gate.md`。
2. **补稿不能把已淘汰稿从候补池放回来。** 安全/历史淘汰后使用完整去重目录，先找其他题材；补入稿仍过所有发布门禁。目录耗尽可少发，不用旧稿凑 3 篇。这个“完整候选目录 + 多层门禁”适合其他内容项目。
3. **feed 数不等于独立出版方。** ScienceDaily 多 feed 曾造成三篇科学稿看似多源、实际同一出版方；Science 目标至少两家独立出版方，且来源邮件阈值只需 2 个 source。大学招募稿也不能仅因提及游泳/网球获得 Fun 加分。
4. **栏目要按新闻主旨与公共后果判断。** 数据中心争议/政府 AI 使用留 News，机器人趣味发明进 Fun；政治/战争不因题材“成人”而自动删除，最终文字须中性、可理解并经独立安全审核。重要性分数是软选择，不可绕过事件或安全门禁。
5. **旧漏斗数字、旧文档和旧本机 checkout 都可能误导。** `docs/pipeline-funnel-audit-2026-09-26.md` 的 40→30→6→3 等是真实历史运行，但其“跨栏目历史查重”“固定 top-10”“Fun 送审 6”“旧稿兜底”已被后续 PR 修改。`run_date` 回填只改编辑日期，不还原当天 RSS/来源轮换快照。调优需保存运行 SHA、候选目录、各层数量、JEV 调用/token、独立安全结果及最终网站同步提交。
6. **可移植的是分层决策，不是儿童项目的阈值。** 其他项目可复用“来源表 → 确定性清洗 → JEV 短文结构化判断 → 同事件目录与题材软多样性 → 编辑模型 → 全文/项目专用审核 → 发布验证”，见 `docs/jev-article-filtering-playbook.md`。AI News 的受众、跨栏查重范围、风险政策和正文长度需独立定义，不能照搬 Kids News 的七天同栏规则或儿童安全阈值。

本次仅作代码/Git/公开入口核对，没有读取生产 Supabase 来源表、重新跑 pipeline 或验证最新 `main` 的首次自然定时结果。最近一次人工运行的质量获用户认可，但使用了较早分支提交，不能证明后来合并的规则已在定时生产运行中生效。该验证由现有 Kids News 监控继续追踪。

## 5. 项目报告与后续会话

未来每次项目更改都按根目录 `AGENTS.md`：在同一个功能分支提交并推送 `.project-atlas/project-status.json`，再从项目仓库根目录以已推送 `HEAD` 调本机报告 API。真实 Atlas ID 是 `kids-news-website`。本机 Brain 写入、Brain GitHub `main`、Atlas 网站发布需分别核验；不要把项目 PR、Brain PR、网站同步提交混为一个 Git 状态。需要交接时，把本文件、项目 PR、source commit、API 结果及待办发给 **Project List** 会话。
