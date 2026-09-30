# Kids News Bot：完整、分步影子流水线

2026-09-30。生产仍是 `news-v2/main` → Supabase → `kidsnews-v2`。
新 Bot 在独立仓库 `grokbot-kidsnews`、VM `/workspace/kidsnews-shadow` 运行。
测试站仅为 https://kidsnews-bot-shadow.vercel.app，不覆盖正式网站。

## 一次命令只走一步

入口：`.venv/bin/python -m pipeline.agent_shadow step --run-dir work/D/run-1`。
每次按 stdout JSON 操作；退出 2 写答卷后重跑同一命令；退出 0 是一个步骤完成，
继续下一条 `next`（VM 上将 `python` 替换为 `.venv/bin/python`）。退出 1 停止报告工具错误；
退出 3 表示已打包，不再生成，进入发布交接。`next` 是兼容别名，同样分步。

| 单元 | 脚本做什么 | Agent 做什么 / 验收 |
|---|---|---|
| registry / prepare | 连接器只读来源与本栏前七天历史；抓标题、摘要、URL；固定当天快照 | 不写数据库，不把无法访问历史当成零条 |
| rank | 校验 ID、评分范围、每栏最多 30、跨栏 ID 唯一 | 元数据排名、同事件归组、分栏、历史判断；News 预留重要稿 |
| originals-栏目-目标 | 每栏先看前 12，不足六篇按六篇补抓；仅扩容需要补稿的栏目 | 无模型调用；News 350–1200、Science 350–1500、Fun 250–1200 原文词数 |
| pick-栏目 | 提供前六篇正文摘录，校验完整编号排序 | 六选三并排序备用；重要 News、题材和出版方多样性 |
| rewrite-稿件 | 共用栏目成稿字数校验，错误仅修答卷一次；仍无效记 rewrite_invalid 并换备用稿 | Easy / Middle / 中文卡片；真实双方立场，不编造观点 |
| review-稿件 | 按现有生产安全阈值判断，失败换目录中备用稿；已通过稿件存盘 | 新会话或子 Agent 仅看本任务；同模型第二遍审核，不读写稿答卷和自评 |
| refill-栏目-目标 | 只扩大缺稿或缺出版方栏目；已满足栏目不抓正文、不重选；仅新候选送补稿挑选 | 优先其他题材；已审核稿保留；不补昨日成品，不做额外同日模型查重 |
| details-稿件 | 复用 filter_keywords 删除不在本槽正文的词；其余无效修一次后省略详情保留正文 | 原文有出处的观点，允许为空；背景不得新增原文之外的具体年份和数字 |
| review-details-稿件 | 逐字段、逐题布尔决策，仅删失败项并告警 | 新会话同模型第二遍审核；核对每题 correct_answer 实际正确性，不只检查是否在选项中 |
| image-稿件 | 下载原网页图片并压缩 WebP；失败显示无图并告警 | 不生成或擅自寻找替代图 |
| pack | 输出三栏三阅读层、英文详情、图片；完整 staging 原子转为 site/ | 查看数量、来源、重要稿及审核警告 |
| publish | 只允许固定 shadow Vercel project / team；提交一次后先核验 | 初次由已有 Vercel 登录的 Mac 维护者部署，VM 不加密钥 |
| verify | 公开读取 manifest + 每个 listing/detail/image 并重算内容 hash | 不能仅凭 deploy success 宣称上线 |
| report | 汇总 metrics、completed-steps、review-results、detail-reviews、image-results、published | 只报告实际测得，区分内容完成和上线完成 |

题材规则：政府和公共事务科技留 News，趣味发明入 Fun；动物生物学留 Science，
动物趣事入 Fun；排除招募、大学录取、讣闻、购物导流。游泳/网球世界大赛、纪录和明星优先。
News 最终缺重要稿、Science 少于两独立出版方仍有告警，不绕过安全凑数。
目录耗尽允许少于三篇新稿。不把不同题材必然不同事件当作数学保证：排名阶段先归组去重。

## 文件、平台替换与耗时

- 交接唯一模型边界：`pipeline/ai_providers/`，原生 Agent 用 request.json / answer.json。
  替换为其他在线 Agent 时，不改抓取、字数、安全阈值、打包代码。
- `input.json` 固定输入；`bodies.json` 缓存原文；`pool-栏目-目标.json` 缓存每次合格池。
- `backfill.json` 的 targets 按栏目记录目标（各栏初始 6，后续每批 +6，最多 30）。
  `editor-state.json` 保存已通过稿件、候选排序和拒稿原因；Science 可保留第四篇审查记录，
  仅在最终三篇中用另一出版方替换一槽，已通过稿不重新生成。
- registry 必须包含 history 数组；按本栏前七天过滤后，三栏合计零条即退出 1，检查连接器。
  缓存的 input.json 也不得静默缺失/清空历史；单栏零条会记录在 metrics.history_counts 中。
- `tasks/<key>/<request_hash>/` 是独立任务，request/answer 不写 API key。
  新目录代表新运行；不能改已完成答卷后继续旧运行。
- `accepted-answer-hashes.json` 固定已消费答卷的原始字节 SHA256；即使仅改空白，重放也退出 1。
  JSON 状态经临时文件 + os.replace 写入；`.run.lock` 防止并发 step，第二条命令退出 1。
- `completed-steps.json` 是已完成单元，`steps.jsonl` 记录单元时间/退出状态。
- `metrics.json`：采集秒数、每篇正文抓取秒数、任务输入/答案字节、交接等待秒数。
  交接等待包含 Bot 思考和人的等待，不是纯推理秒数；没有模型账单不能宣称 token/费用为零。
- VM hostname 才推私有 logs 分支；位于 `D/run-1/steps.jsonl`，Mac 测试不会推日志。
- `publish` 使用 Mac 已登录 Vercel CLI，不新增 VM secret；自动发布尚未配置。
  发布交接必须取回同一次运行的完整 `site/`（包括 payloads、article_payloads、article_images、
  shadow-run.json 和静态入口）、`done.json`、`review-results.json`、`detail-reviews.json`、
  `image-results.json`、`metrics.json`，保留相对目录结构。不要只复制 site/ 或添加 VM 密钥。
  通过 Bot 的文件下载功能取回到 Mac 新 run-dir；比对下载前后 shadow-run.json 的 content_hash，
  并核对九篇数量、图片和审核警告后，维护者才能显式 publish。VM 文件下载尚待首测，
  没有验证下载完成时不得部署。不要把 tasks/、环境文件、.vercel/ 或凭据打入下载包。
  发布期间断线/超时可能是结果不确定，先 verify，不要连续重发。
- `deployment-attempt.json` 在 Vercel 命令之前写入。有标记但未 published 时 publish 只返回 verify。
  只有公开内容核验明确失败并写入 verify-failure.json，才可显式
  `publish --retry-after-failed-verify`；网络超时不是明确失败。counts 合计零篇拒绝发布。
- rank/pick 属关键答卷，修一次仍无效退出 1；rewrite/details 的模型答卷无效按上表降级。
  工具错误不伪装为模型拒稿。历史、身份、请求或完成答卷 hash 不可绕过。

## 验证范围

离线假答卷回归使用 Python 3.10，覆盖每栏 24 篇完整目录、Science 单栏补稿不改变 News
抓取/挑选哈希、审核淘汰换备用、Science 两出版方、News 重要稿、先 12 后每批 6 抓取，
以及真实 AgentFilesProvider 的退出 2 → 写答卷 → 退出 0 命令行握手（stdout 单行 JSON）。
还覆盖字数修正耗尽、详情字段/题目降级、原子写、并发拒绝、完成答卷 SHA256、发布超时标记、
明确失败才可重发、空部署拒绝及图片字节参与公开内容 hash。全部使用假抓取/答卷/部署。
假答卷不是 Grok 真实编辑质量验证，未运行 VM 和真实稿件不能标记已验收。
保留原生产，暂不创建例行任务、不自动切正式站。
# Optional autonomous editor (2026-09-30)

The opt-in `prepare --editor-mode autonomous` skips mandatory thirty-ranking/six-pick stages,
starts with three originals per category, preserves approved stories, and expands only a deficient
category using reserves, unused feed metadata or temporary public-source discovery. The default
staged workflow below is unchanged. See [autonomous mode](KIDSNEWS-AUTONOMOUS-SHADOW.md)
for budgets, shadow-only role routing, evidence/URL safety, offline tests and real-run limitations.
