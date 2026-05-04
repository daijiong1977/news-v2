# Kids News (news-v2) — 全项目设计文档

> **目的**：让任何人（包括没有此 session 上下文的 Claude / 未来的你）一份文档读完就能完整理解这个项目：怎么跑、出问题怎么修、bug 系统怎么用。本文档是 source of truth；session 丢了不影响。
>
> **最后更新**：2026-04-29
> **状态**：v1.0 — 项目主要功能上线，feedback + autofix 闭环工作

---

## 1. 项目是什么

**news.6ray.com** （a.k.a. kidsnews · 21mins）—— 给孩子的每日新闻网站，每天自动从 RSS 拉新闻，LLM 改写成 kid-friendly 的 News / Science / Fun 三个分类、每类 3 篇 top stories、每篇分 Sprout（易）/ Tree（难）/ 中文 三个版本，加上 keywords / why-it-matters / 讨论问题 / 配图，pack 成静态站点上线。每天读 21 分钟。

**域名**：
- `news.6ray.com` — 主站（也叫 kidsnews.21mins.com）
- 后台 admin：`news.6ray.com/admin`
- 控制面板：`news.6ray.com/autofix`（autofix 队列管理）

**核心仓库**：
- `~/myprojects/news-v2` — 主代码库（pipeline + website + admin）
- `daijiong1977/kidsnews-v2` — 静态站点部署仓（Vercel 自动 build）

---

## 2. 端到端架构

```
                                   ┌──────────────────────────┐
                                   │      RSS 新闻源（多家）     │
                                   └────────────┬─────────────┘
                                                ↓
                              [GitHub Actions] daily-pipeline.yml
                              (每天 admin-configured 时间 +/- 15min)
                                                │
        ┌───────────────────────────────────────┴───────────────────────────────────────┐
        │                                                                               │
        │   pipeline.full_round 模块链：                                                  │
        │   1. mining           — RSS 拉新闻                                              │
        │   2. phase_a_light    — 第一轮 LLM 过滤（明显垃圾）                              │
        │   3. stage1_forbidden — keyword filter（性 / 暴力 / 政治极端）                   │
        │   4. phase_a_probe    — 深度 vetting（kid-friendliness）                       │
        │   5. stage2_curator   — 选 top-3 per category（带 source diversity 校验）       │
        │   6. verify           — 事实核查                                                │
        │   7. rewrite          — LLM 改写为 Sprout / Tree / 中文，加 keywords/why         │
        │   8. stage3_safety    — 最后一道安全审查                                         │
        │   9. enrich           — 填补 questions / discussion / background_read           │
        │  10. persist          — 写 redesign_stories 表                                  │
        │  11. pack_and_upload  — 打包 zip → Supabase Storage → 触发 kidsnews-v2 sync    │
        │                                                                               │
        └───────────────────────────────────────┬───────────────────────────────────────┘
                                                ↓
                                       Supabase Storage
                                ┌─────────────────────────────────┐
                                │ redesign-daily-content/          │
                                │   YYYY-MM-DD/                    │
                                │     payloads/                    │
                                │       articles_<cat>_<lvl>.json  │
                                │     article_payloads/            │
                                │       payload_<sid>/<lvl>.json   │
                                │     article_images/              │
                                │   latest.zip  ← 主部署包          │
                                └────────┬────────────────────────┘
                                         ↓
                   [GitHub Actions in kidsnews-v2 repo]
                   sync-from-supabase.yml — pulls latest.zip,
                   unzips into site/, commits, pushes
                                         ↓
                                     [Vercel]
                          自动 build + deploy news.6ray.com
                                         ↓
                                  Kids 访问 news.6ray.com
```

---

## 3. 三套子系统（这次 session 加的）

### 3.1 用户反馈系统（Feedback）

**目的**：网站访客通过 💬 按钮反馈 bug / 建议 / 内容意见，自动 triage 后进 GitHub issue 给你审。

**数据流**：
```
用户网站 💬 按钮
    │ POST
    ↓
edge fn: submit-feedback   ─→ Supabase 表: redesign_feedback (status=new)
                                      │
                                      │ 每天 04:00 UTC cron
                                      ↓
                            pipeline.feedback_triage 跑
                                      │ DeepSeek 分类
                                      ↓
            classification ∈ {bug, suggestion, content, noise, duplicate}
                  │              │              │             │
              GH Issue 开       GH Issue        GH Issue   auto-dismiss
                  │              │              │
                  │              └──── 你审 issue ───┐
                  │                                  │
                  ↓                                  ↓
        admin → "→ Bug record"                  Resolve / Dismiss / 改代码
                  │
                  ↓
        cp _template.md docs/bugs/<date>-<slug>.md
        填 5 段（Symptom / Root cause / Fix / Invariant / Pinning test）
        加 INDEX.md 一行
                  │
                  ↓
        改代码 commit 带 `Bug-Record:` trailer
        commit-msg hook 校验
                  │
                  ↓
        republish-bundle 部署
```

**文件**：
- `supabase/functions/submit-feedback/index.ts` — 接收端
- `pipeline/feedback_triage.py` — 分类器
- `.github/workflows/feedback-triage.yml` — cron
- `website/home.jsx` (FeedbackButton + FeedbackModal) — 前端入口
- `website/admin.html` (FeedbackTab) — triage UI
- DB 表：`redesign_feedback`

### 3.2 质量保证 + 自动修复系统（Quality Digest + Autofix）

**目的**：每天 pipeline 跑完后 1 小时检查 9 篇文章质量，机械问题（长度超限）当场 trim 修，复杂问题（关键词漏、body 太短、图片缺）入队等你点按钮触发本地 Claude Code agent 修。

**数据流**：
```
daily-pipeline 完成
    │ workflow_run trigger
    ↓
[GH Actions] quality-digest.yml （sleep 1h）
    │
    ├─→ pipeline.quality_autofix
    │     ├─ 机械问题 (body trim / why trim) → 改 storage payload
    │     └─ 复杂问题 → INSERT redesign_autofix_queue (status=queued)
    │
    └─→ pipeline.quality_digest
          ├─ 扫 storage 9 篇文章质量指标
          ├─ 扫 redesign_autofix_queue 待办列表
          └─ 发邮件给 redesign_admin_users 里所有 email：
              ├─ Clean day: 大绿 panel "🎉 Today everything is good!"
              └─ Issue day: 红 panel 列出每个 issue + 怎么修
                            + 紫色按钮 "🛠️ Review pending fixes →"
                              ↓
                        news.6ray.com/autofix
                        (Vercel 静态页 + JS)
                              ↓
                        每个 queue item 三个按钮：
                            🛠️ Fix    → JS PATCH status=fix-requested
                                          ↓
                                  本地 Claude Code scheduled task
                                  (3am + 10am 触发, 用户 Mac 上)
                                          ↓
                                  读 redesign_autofix_queue 拿一行
                                          ↓
                                  Agent 调度 (kidsnews-bugfix skill)
                                  读 issue + 定位代码 + 写 fix
                                          ↓
                                  git commit + push + gh pr create
                                          ↓
                                  status='resolved' 写回 (or
                                  ABANDONED after 2 retries)
                            🚫 Dismiss → JS PATCH status=dismissed
                            ✓ Resolved → JS PATCH status=resolved
```

**文件**：
- `pipeline/quality_digest.py` — 每天发邮件
- `pipeline/quality_autofix.py` — 机械修复入队
- `pipeline/autofix_apply.py` — pipeline-side 直接处理 (DeepSeek + image regrab)，处理不了的标 escalated
- `~/.claude/scheduled-tasks/news-v2-autofix/SKILL.md` — 本地 scheduled task 的 prompt (用户 desktop 配置)
- `.claude/settings.local.json` — pre-approved permissions for the scheduled task
- `docs/AUTOFIX-SCHEDULED-TASK.md` — setup + ops guide
- `website/autofix.html` — Vercel 静态控制面板
- `.github/workflows/quality-digest.yml` — workflow_run trigger + sleep + 跑
- DB 表：`redesign_autofix_queue`

> **历史**: 2026-04-29 → 2026-05-04 用过基于 launchd + `claude -p` 的本地 daemon 路径
> (autofix_consumer.py + scripts/autofix-daemon.sh + KidsnewsAutofix.app + URL scheme).
> 2026-05-04 拆掉切换到 Claude Code scheduled tasks. 见
> `docs/bugs/2026-05-04-autofix-scheduled-task-migration.md` 和
> `docs/bugs/2026-04-29-autofix-token-starvation.md` (前一次的相关教训).

### 3.3 Bug 记录系统（Bug Records）

**目的**：每次修 bug 留一份 5 段格式的 markdown，commit-msg hook 强制执行，让未来 session（哪怕 cold-read）也能修 regression。

**结构**：
```
docs/bugs/
├── _template.md            ← 复制起点
├── INDEX.md                ← 全部 record 索引（grep 入口）
├── HOW-TO-USE.md           ← 中文使用手册
├── YYYY-MM-DD-<slug>.md    ← 单条记录（每个修过的 bug）
└── ...

.githooks/commit-msg        ← fix( 提交必须带 Bug-Record: trailer
```

**Record 5 段**：
1. **Symptom** — 用户原话 / 截图 / 复现路径
2. **Root cause** — 为什么会发生（深层原因，引用 file:line）
3. **Fix** — PR / commit + 改了什么
4. **Invariant** — 一句规则，未来改这块代码不能违反
5. **Pinning test** — 一个测试 / smoke 脚本 / 30 秒手工复测路径

**Hook 规则**：
- `fix(...)` 或 message 含 `bug:` 的 commit → 必须带 `Bug-Record: docs/bugs/<file>.md` trailer
- 路径必须存在 + 必须在 `INDEX.md` 里登记
- `feat(`/`docs(`/`chore(`/`refactor(` 不需要

**激活**（每个 clone 一次）：
```bash
git config core.hooksPath .githooks
```

---

## 4. 现有 bug records（截至 2026-04-29）

详见 `docs/bugs/INDEX.md`。session 做的修复都有 record：

| Date | Sev | Area | Slug |
|---|---|---|---|
| 2026-04-30 | medium | infra | supabase-edge-fn-html-blocked |
| 2026-04-29 | medium | infra | autofix-token-starvation |
| 2026-04-29 | high | website | search-click-wrong-article |
| 2026-04-28 | high | website | archive-route-404 |
| 2026-04-28 | high | website | archive-click-race |
| 2026-04-28 | medium | website | archive-slow-load |
| 2026-04-28 | high | pipeline | news-source-diversity |
| 2026-04-28 | medium | pipeline | keyword-stem-mismatch |

每条 record 都有完整的 root cause + invariant + pinning test，未来 session 修同一区域代码必须先 grep INDEX。

---

## 5. 外部依赖盘点

| 系统 | 用法 | 凭据存哪 |
|---|---|---|
| **Supabase** | DB + Storage + Edge Functions + Vault | service key in `.env` / GitHub secret |
| **DeepSeek API** | LLM 调用（vetting / rewrite / triage） | `DEEPSEEK_API_KEY` |
| **Gmail SMTP** | 发邮件（quality digest, parent digest） | `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD` in Supabase Vault |
| **Anthropic Claude Code** | 本地 agent (autofix consumer) | 用户 Claude Pro 订阅 |
| **GitHub Actions** | 所有 cron + workflow | repo secrets |
| **Vercel** | news.6ray.com 部署（kidsnews-v2 repo） | Vercel auto-deploy on push |
| **Tavily / EXA** | 来源补充搜索（少量） | API key in env |
| **Jina** | 网页提取（少量） | API key in env |

---

## 6. 关键 GitHub Workflows

| 文件 | 触发 | 干啥 |
|---|---|---|
| `daily-pipeline.yml` | 每 30min poll + admin cron + dispatch | 跑 full_round（mining → upload） |
| `quality-digest.yml` | daily-pipeline 完成 + 1h | quality_autofix → quality_digest 邮件 |
| `feedback-triage.yml` | 每天 04:00 UTC + dispatch | DeepSeek 分类 feedback → 开 GH issue |
| `republish-bundle.yml` | dispatch | 不重新 mining，只刷新静态资源到 latest.zip |
| `retention-cleanup.yml` | 每天 03:00 UTC + dispatch | 删 30 天前的旧 storage |
| `verify-source.yml` | dispatch | 单独验证某个 RSS 源 |
| `parent-digest.yml` | 每天 10:00 UTC | 给家长发孩子读了哪些文章 |

---

## 7. 操作手册（OPERATIONAL TASKS）

### 7.1 修 bug 的标准流程

1. 出问题 → 用户提交 feedback OR pipeline 自己发现
2. triage 分类 → 真 bug 进 GH issue
3. **修之前**：`grep -ri "<相关关键词>" docs/bugs/` 查 invariant，**不要破坏**
4. 改代码 + 测
5. `cp docs/bugs/_template.md docs/bugs/<date>-<slug>.md`
6. 填 5 段
7. 在 `docs/bugs/INDEX.md` 加一行
8. commit，message 末尾：
   ```
   Bug-Record: docs/bugs/<date>-<slug>.md
   ```
9. push
10. 视情况 dispatch `republish-bundle` 部署到生产

### 7.2 加新管理员（让他们也收 quality digest）

```sql
INSERT INTO public.redesign_admin_users (email)
VALUES ('newadmin@example.com');
```
或在 `news.6ray.com/admin` → Admins tab 里加。下次 quality digest 自动发给所有 admin。

### 7.3 添加 / 删除 RSS 源

`news.6ray.com/admin` → Sources tab 编辑。改完后下次 daily-pipeline 用新源。

### 7.4 看某天的 quality

打开 `news.6ray.com/autofix`（永久 URL）—— 队列空就显示 "🎉 Today everything is good!"。

### 7.5 强制清空 autofix 队列

scheduled task 自动在 3am + 10am 跑。要立刻处理：在 Claude Code Desktop
sidebar 找到 "news-v2-autofix" task，点 **Run now**。
没装过的话先看 `docs/AUTOFIX-SCHEDULED-TASK.md`。

### 7.6 紧急重新部署网站（不重新 mining）

GitHub Actions → `republish-bundle.yml` → Run workflow。3 分钟左右生效。

### 7.7 改 pipeline 触发时间

`news.6ray.com/admin` → Pipeline tab → Cron schedule 编辑。立刻生效（30min poll 自动认）。

### 7.8 改 retention（多少天后清旧数据）

admin → Pipeline tab → Retention card。当天晚 03:00 UTC 生效。

---

## 8. 排错速查

| 现象 | 先看哪 |
|---|---|
| 网站没更新 | `gh run list -R daijiong1977/news-v2 --workflow=daily-pipeline.yml` 看跑过没 |
| 页面图加载失败 | `archive-click-race` / `search-click-wrong-article` bug records |
| 邮件没收到 | 1) Gmail Spam folder 2) `daedal1977@gmail.com` 发件账号是否在 Vault |
| 邮件里看到 raw HTML 源代码 | subject 里有 emoji/em-dash 触发 RFC 2047 编码冲突 → 用 ASCII subject |
| autofix 队列卡 fix-requested 不动 | 1) Claude Code Desktop 关了 → 下次 launch 补跑 2) scheduled task 没创建 → 看 `docs/AUTOFIX-SCHEDULED-TASK.md` 3) `.claude/settings.local.json` 缺 → 第一次 fire 卡 permission |
| 队列里的 item 反复失败 | `attempts >= 3` 后状态变 `escalated`，需手工排查 agent log |
| Edge function 返回 HTML 但浏览器显示成 text | `supabase-edge-fn-html-blocked` bug record（Supabase 强制 sandbox） |
| pipeline 跑不动一直 in_progress | 检查 60 min timeout；可能是 DeepSeek API quota |
| 邮件 button 点了浏览器没反应 | 你 Mac 上 KidsnewsAutofix.app 没装/被卸；重跑 build-autofix-app.sh |

---

## 9. Memory + Cross-references

- `~/.claude/projects/-Users-jiong/memory/MEMORY.md` — Claude session 持久 memory（用户偏好、项目状态等）
- `~/myprojects/news-v2/docs/gotchas.md` — 没具体 bug 但值得 cold-read 的 silent edge cases
- `~/myprojects/news-v2/docs/bugs/INDEX.md` — 全部已修 bug records 的索引
- `~/myprojects/news-v2/docs/bugs/HOW-TO-USE.md` — bug record 系统中文手册
- `~/myprojects/news-v2/docs/superpowers/specs/` — 各个 feature 的 design spec

---

## 10. 后续想做的（已记录但 deferred）

- **Auto-dedup feedback**：现在只在用户自己声明 duplicate 时才合并，未来 LLM 主动检测
- **Issue → Project board 自动 link**：triage 开 issue 时自动加 milestone
- **Source pool 太窄告警**：source diversity 触发 fallback 时应该警告而不是静默
- **iOS / iPad 客户端**：Memory 里有备忘说"先把网站做完再考虑"
- **每天 metrics 报告**：用户人数、阅读完成率、popular categories
- **更多 admin 用户邮件配置**：现在 quality_digest 发给所有 admin；未来可能想分级（dev 收技术，编辑收内容）

---

## 11. 项目历程关键节点

- **2026-04-20**：本地开发起步，搭 pipeline 骨架
- **2026-04-24**：Supabase 后端 + DB schema 初版
- **2026-04-25**：admin panel 上线
- **2026-04-27**：news.6ray.com 域名上线，第一封 parent digest 邮件成功
- **2026-04-28**：archive 功能、search 功能、retention cleanup
- **2026-04-29**（这次 session）：feedback 系统、autofix 系统、bug record 系统、所有 cross-system gotchas 落记录
- **2026-04-30**：所有子系统稳定，文档化收尾

---

## 12. 紧急联系

- 主要 admin email: `daedal1977@gmail.com`（也是邮件 sender）
- Workspace alias: `self@daijiong.com`
- Supabase project ref: `lfknsvavhiqrsasdfyrs`
- GitHub repo: `daijiong1977/news-v2` + `daijiong1977/kidsnews-v2`
- 部署域名：`news.6ray.com`（CNAME → kidsnews-v2.vercel.app）

---

**未来读这份文档的 Claude / 你自己：**
1. 先 grep `docs/bugs/INDEX.md` 看相关区域有没有 invariant 要保护
2. 改之前看 `docs/gotchas.md`
3. 改完留 record + 加 INDEX 行 + commit 带 trailer
4. 这套循环走通就保护了项目长期健康
