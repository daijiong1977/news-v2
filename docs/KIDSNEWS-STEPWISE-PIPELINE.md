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
| originals-6 | 每栏先看前 12，不足六篇按六篇补抓；缓存正文、词数、图片地址 | 无模型调用；News 350–1200、Science 350–1500、Fun 250–1200 原文词数 |
| pick-栏目 | 提供前六篇正文摘录，校验完整编号排序 | 六选三并排序备用；重要 News、题材和出版方多样性 |
| rewrite-稿件 | 共用栏目成稿字数校验，错误仅修答卷一次 | Easy / Middle / 中文卡片；真实双方立场，不编造观点 |
| review-稿件 | 按现有生产安全阈值判断，失败换目录中备用稿 | 独立提示审核全部可见稿件，核对原文事实，不读写手自评 |
| refill-N | 安全淘汰后不足三篇或 Science 不足两出版方，继续扩大同日目录 | 优先其他题材；不补昨日成品，不做额外同日模型查重 |
| details-稿件 | 校验 slot、关键词在本槽正文、六道四选一题及答案 | 关键词、测验、背景、结构、重要性、不同视角 |
| review-details-稿件 | 不通过就去掉附加内容并明确 warning | 独立审核背景/解释/问题/观点的安全、中立、事实和答案 |
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
- `input.json` 固定输入；`bodies.json` 缓存原文；`pool-N.json` 缓存每次合格池。
- `tasks/<key>/<request_hash>/` 是独立任务，request/answer 不写 API key。
  新目录代表新运行；不能改已完成答卷后继续旧运行。
- `completed-steps.json` 是已完成单元，`steps.jsonl` 记录单元时间/退出状态。
- `metrics.json`：采集秒数、每篇正文抓取秒数、任务输入/答案字节、交接等待秒数。
  交接等待包含 Bot 思考和人的等待，不是纯推理秒数；没有模型账单不能宣称 token/费用为零。
- VM hostname 才推私有 logs 分支；位于 `D/run-1/steps.jsonl`，Mac 测试不会推日志。
- `publish` 使用 Mac 已登录 Vercel CLI，不新增 VM secret；自动发布尚未配置。
  把 Bot 的 `site/` 取回到 Mac 后，用同一个 run-dir 的 publish/verify 命令。
  发布期间断线/超时可能是结果不确定，先 verify，不要连续重发。

## 验证范围

离线假答卷回归覆盖分步暂停、全流程恢复、字数、安全、详情 slot/关键词/测验校验、
发布目标锁定、已提交不重复部署，以及旧站/内容 hash 不匹配不能确认上线。
假答卷不是 Grok 真实编辑质量验证，未运行 VM 和真实稿件不能标记已验收。
保留原生产，暂不创建例行任务、不自动切正式站。
