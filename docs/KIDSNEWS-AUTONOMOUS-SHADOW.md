# 自主编辑影子模式 — 2026-09-30

## 状态与边界

这是 PR #86 的 **可选影子模式**，并非生产替换。Bot 快照在
`grokbot-kidsnews/codex/stepwise-full-shadow`（PR #1）。默认仍是 staged。
本轮没有真实模型调用、数据库写、部署、邮件或向 Bot 发消息；尚未证明原生 Grok
搜索工具、TLS 实际抓取、会话隔离、实际费用和最终编辑质量。

共享源码先修改 `/Users/jiong/myprojects/news-v2-agent-provider`，测试后导出到
`/Users/jiong/myprojects/grokbot/grokbot-kidsnews`。UPSTREAM.json 记录共享 HEAD；
生产 news-v2/main、kidsnews-v2、full_round、news_rss_core 的编排不变。

## 两种模式

| 阶段 | staged（原模式） | autonomous（新模式） |
| --- | --- | --- |
| 输入 | 来源表 RSS 元数据 + 同栏七天历史 | 相同；来源是种子，不是排他名单 |
| 初选 | 目录至多30、前12原文、六选三 | plan 直接选3 + 最多3备用；先只抓3原文 |
| 后续 | 每次局部扩容6 | 原目录备用每批3；耗尽后仅缺稿栏目追加至多3 |
| 补选来源 | 固定目录 | 优先使用尚未选中的 feed 元数据；必要时原生搜索新文章 |
| 改写和审核 | 持久化编辑器、三语审核、逐字段详情审核 | 同一工具链；额外复核历史和本栏已通过事件 |
| 最终 | 独立影子内容包、单独 publish/verify | 相同，不能直写生产 |

不用为了满足固定漏斗而让 Agent 重排30篇或再六选三。代码仍重新抓取原文，
不接受 Agent 自报的正文或出版方。重要成人政治、公共事务科技、平静战争/死亡事实
可以留 News，但最终稿必须中立、适龄；双方观点必须有原文归属，不为平衡而编造。
Science 生物学留 Science；动物趣事/趣味科技进 Fun；禁止招募、讣闻、购物导流。

每篇仍检查本栏目过去七天（不含当天覆盖稿）的 URL 和事件。审核收到完整原文、
三语可见稿、同栏历史和已通过稿的标题/原文摘要；facts_supported 和 event_clear
必须都为 true，安全分由代码执行原有门槛。不确定不能当作通过。

News 三篇已通过但没有重要稿时，继续寻找 importance>=3 的合格备用稿，
只替换一个最终展示槽，保留之前通过稿的审核记录。Science 同理寻找第二家出版方。
预算耗尽允许少于三篇，或重要稿/出版方缺口明确警告，不从昨日成品补旧稿。

## 可调预算

`pipeline/agent_shadow_autonomous.py:LIMITS`：

- 全轮至多36次正文抓取，尝试前占用预算，失败不返还。
- 每栏至多2轮扩展；每轮 existing + 新 articles 合计至多3。
- 原生搜索任务要求最多3个查询、6个页面。**这是 Agent 指令，不是浏览器配额的代码证明**；
  首测须看平台轨迹。代码强制限制交回 URL 数和后续受控抓取。
- 每页/图片至多2MB、20秒、4次跳转；只接受公共 HTTPS/443。
- DNS 每跳检查、连接固定公共 IP，同时保留原域名 TLS 证书/SNI 校验；禁代理、凭据、私网。
- 原图只来自抓取页面的 og:image，使用相同受控工具；最多1200边、2000万像素，失败省略并记录。

`pipeline/agent_shadow_providers.py`：至多120个不同任务、120次 HTTP 尝试；
一轮新任务/HTTP 调用在首任务后一小时停止。该限制不是模型 dollar 预算，也不能
强制终止已经在云端执行的原生搜索。每次不合格答卷仍只允许一次修正。
HTTP 超时/异常写 attempted 状态，不盲重试；使用新运行目录并核对账单。

新增来源只写运行目录 source-suggestions.json，状态 temporary_not_enabled；
不会自动启用来源表。最终抓取域名（含既有 publisher_key 品牌别名）作为出版方依据，
不是全球出版集团所有权数据库；不同未知域名仍可能属于同一集团，首测需人工确认。

## 启动与模型替换

先按既有 SKILL 读取真实来源/历史 connector registry，然后在新的运行目录执行：

```sh
.venv/bin/python -m pipeline.agent_shadow prepare --run-dir work/D/autonomous-1 --date D \
  --registry work/D/registry.json --editor-mode autonomous
.venv/bin/python -m pipeline.agent_shadow step --run-dir work/D/autonomous-1
```

每次只完成一个单位，退出2写答卷；审稿须新会话/子 Agent，只读当前请求，
不能带入写作上下文。模式按运行目录冻结，不能在恢复中切换。
只在 discover-* 任务允许搜索；plan、rewrite、review、details 不允许自行浏览。
缺工具就返回空 articles，不假造找到的文章。

默认所有判断用原生 Agent，不需要模型 API Key。也可 prepare 时传
`--providers-config /安全本地路径/providers.json`，配置会复制到运行目录并冻结。
格式如下（只能存环境变量名字，不能存 Key）：

```json
{
  "roles": {
    "editor": {"type": "native"},
    "discovery": {"type": "native"},
    "write": {
      "type": "http",
      "model": "deepseek-chat",
      "endpoint": "https://api.deepseek.com/chat/completions",
      "key_env": "KIDSNEWS_SHADOW_MODEL_KEY"
    },
    "review": {"type": "native"},
    "details": {"type": "native"}
  }
}
```

HTTP 与文件交接共享答卷缓存、校验与 SHA256。配置修改必须新建运行目录。
API Key 由调用进程环境提供，不进入请求、日志或 Git，不能把它直接放到 Bot VM。
纯文本 HTTP 不具备搜索工具，所以 discovery 只接受 native；其他带工具的在线 Agent
可按相同 request/answer 协议接入，但平台安装/能力授权不是此配置自动完成的。
没有 native 模型 ID 的自动选型功能，使用运行 Agent 的当前模型。

## 首次真实测试验收（尚未执行）

同日 registry 分别创建 staged 和 autonomous 新目录，只发布到影子站；不覆盖生产。
比较九篇是否值得读、重要 News、中立三语卡片、Science 实际出版方、Fun 趣味性，
以及候选/正文/搜索/模型次数、真实费用、拒稿原因、耗时。原生 token 未提供时写未知，
不能用任务数当 token。先人工确认真实搜索、TLS/SNI兼容和会话隔离，再考虑部署。

主要记录：input.json、autonomous-catalog.json、autonomous-audit.json、provider-audit.json、
bodies.json、editor-state.json、backfill.json、review-results.json、source-suggestions.json、
metrics.json、steps.jsonl、accepted-answer-hashes.json、done.json、site/shadow-run.json。
HTTP usage 按服务返回保存；原生没有 token 计数，不虚构。失败和部分成功均要列明。

## 离线测试

`pipeline/test_agent_shadow_autonomous.py` 的核心回归先失败后实现，另补防御性测试：直接三篇、只补缺栏、
保留过审稿、事件淘汰、临时来源、复用深层元数据、出版方跳转、重要稿备用、正文预算、
私网/非HTTPS/凭据/端口、固定IP和私网跳转、真实文件交接及答卷改动、HTTP缓存/未知超时、
模型路由和安全图片 WEBP。所有模型、connector、抓取和部署均离线替身。
与既有109项回归一起在 Python3.10.20 下运行：**131 passed**（新增22项），
只有已有 gotrue 弃用警告。共享仓最终这一轮用时3.15秒；不是实际生成的模型耗时。

```sh
python -m pytest -q -p no:cacheprovider pipeline/test_agent_shadow_autonomous.py \
  pipeline/test_agent_shadow_review_fixes.py pipeline/test_agent_shadow.py \
  pipeline/test_agent_shadow_publish.py pipeline/test_shadow_site.py pipeline/test_ai_providers.py \
  pipeline/test_safety_quality.py pipeline/test_quality_rca.py pipeline/test_wc_repair.py \
  pipeline/test_cadence_calibrate.py
```

## 可复用到 AI News 等项目

复用 TaskRouter（角色与请求协议）、AutonomousEditor 的局部补充策略、受控 HTTP 抓取、
原文证据哈希、按栏目/主题历史、通过稿持久化和 attempted→verify 发布协议。
儿童阈值、三语格式、七天窗口和栏目定义属于 Kids News，不能不加修改地复制为通用规则。
