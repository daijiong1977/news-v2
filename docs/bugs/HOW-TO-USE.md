# 用户反馈 + Bug 记录系统 — 使用手册

这是一套两层系统：
1. **用户反馈** — 网站访客通过右下角 💬 按钮提交反馈，落到 Supabase 表 `redesign_feedback`，admin 后台可查看 + triage。
2. **Bug 记录** — 每个修过的 bug 在 `docs/bugs/` 留一份固定模板的 markdown，未来 session（哪怕是新开的、没有任何上下文的 Claude）都能 cold-read 找到根因 + 不变量 + 回归测试。
3. **commit-msg hook** — 防止 fix 提交时偷懒不写记录。

---

## 一、用户怎么提交反馈？

网站任何页面右下角都有一个浮动 💬 按钮（onboarding 阶段隐藏）。点开会弹出 modal：

- 选 type：🐞 Bug / 💡 Suggestion / 📰 Content / 💬 Other
- 写一段话（5–4000 字）
- 点 Send → 直接落库，匿名

服务器侧：edge function `submit-feedback` 验证 + rate limit（同一 IP 每分钟 5 条）。

---

## 二、你怎么 triage 反馈？

打开 `https://news.6ray.com/admin.html`（或本地 admin.html），登录，点 **💬 Feedback** tab：

| 操作 | 含义 | 何时用 |
|---|---|---|
| **→ Bug record** | 这是真 bug，转成正式 bug record | 用户描述了一个可复现的问题，需要修代码 |
| **Resolved** | 已解决，不需要 record | 改了配置 / 改了文案 / 内容调整就好的小事 |
| **Dismiss** | 重复 / 垃圾 / 无法行动 | spam、模糊不清的诉求、纯情绪 |
| **Reopen** | 重新放回 new | 之前 triage 错了 |

点 "→ Bug record" 时会让你填一个路径，例如 `docs/bugs/2026-04-30-feedback-button-mobile-overlap.md`。系统不会自动创建文件，你需要手动做下一步：

---

## 三、怎么写一份 bug record？

```bash
# 1. 复制模板
cp docs/bugs/_template.md docs/bugs/2026-04-30-<slug>.md

# 2. 填内容（5 段：Symptom / Root cause / Fix / Invariant / Pinning test）

# 3. 在 INDEX.md 加一行（这一步很关键，否则 commit hook 会拒绝）
#    | 2026-04-30 | high | website | [<slug>](2026-04-30-<slug>.md) | <一句症状> | <关键词> |

# 4. 修代码 + commit，commit message 末尾加：
#    Bug-Record: docs/bugs/2026-04-30-<slug>.md
```

模板的 5 段填法（把这条记牢）：

| 段 | 写什么 | 不要写什么 |
|---|---|---|
| **Symptom** | 用户原话 / 截图 / 复现路径（URL + level + 日期） | 解决方案 |
| **Root cause** | 为什么会发生（深层原因，不是表面）；引用 file:line；命名被违反的不变量 | 怎么修的 |
| **Fix** | PR / commit SHA + 改了哪些 file:line + 为什么这么改 | 长篇大论 |
| **Invariant** | 一句规则，未来改这块代码不能违反 | 模糊的"小心点" |
| **Pinning test** | 一个测试 / smoke 脚本 / 30 秒手工复测路径 | "应该没问题了" |

写得越严，未来的 session（包括 Claude）越能独立修 regression。

---

## 四、commit-msg hook 是怎么工作的？

每个 clone 都需要激活一次：

```bash
git config core.hooksPath .githooks
```

激活后，任何 `fix(...)` 或 message 含 `bug:` 的 commit **必须**带：

```
Bug-Record: docs/bugs/<some-existing-record>.md
```

否则 commit 被拒绝。规则：
- 路径必须真实存在
- 路径必须以 `docs/bugs/` 开头
- 必须在 `docs/bugs/INDEX.md` 里有引用（防止你写了 record 但没登记进索引）

`Merge` / `Revert` / `fixup!` / `squash!` / `feat(` / `docs(` / `chore(` / `refactor(` 不需要。

要绕过：把 commit 前缀从 `fix(` 改成更准确的 `chore(`/`refactor(`/`docs(`，**不要**用 `--no-verify`（违背系统初衷）。

---

## 五、Phase 3 — 自动 triage（已上线）

已经搭好了，**每天 04:00 UTC** 自动跑一次：

1. 读 `redesign_feedback.triaged_status='new'` 且过去 48 小时内的行
2. DeepSeek V4 Flash 分类成 `bug` / `suggestion` / `content` / `noise` / `duplicate` + 抽 summary + 建议 slug + bug 的 severity
3. **noise** → 自动 dismiss（写入 `triaged_note`）
4. 其它三类 → 自动开一个 GitHub issue（带原文 + LLM 分析 + 下一步 checklist），URL 写回 `triaged_note` + `gh_issue_url`
5. 状态保留 `'new'`，等你审 issue 后再用 admin 的 "→ Bug record" 转

**手动触发**（用于测试或紧急 triage）：

```bash
# Repo: github.com/daijiong1977/news-v2 → Actions → "Feedback triage" → Run workflow
# 选项：
#   - dry_run: true   不写 DB、不开 issue，只在日志里看分类结果
#   - since_hours: 48  默认；想清旧库存可以拉到 168 / 720
#   - max_rows: 50     成本上限，单跑最多分类多少条
```

**输出**：每跑一次会上传 `feedback-triage-<run-id>.json` artifact，30 天保留期，里面是完整分类结果（含 LLM rationale），方便你回看。

**成本**：DeepSeek V4 Flash 约 $0.0005/feedback，100 条/天 = $0.05/天。

**配置**：`pipeline/feedback_triage.py` + `.github/workflows/feedback-triage.yml`。新加的 DB 列：`triage_classification` / `triage_severity` / `triage_summary` / `triage_slug` / `gh_issue_url` / `gh_issue_number` / `triage_at`（admin Feedback tab 已经显示这些字段相关的 triaged_note）。

**下一步要不要做的**：
- 自动给 GitHub issue 加 milestone / project board
- LLM 主动检测 dedup（现在只在 user 自己声明 duplicate 时才合并）
- 把每天的 digest 邮件发到你邮箱，省得登 GitHub 看

---

## 六、文件位置参考

| 文件 | 作用 |
|---|---|
| `docs/bugs/_template.md` | 复制起点 |
| `docs/bugs/INDEX.md` | 全部 record 的索引（grep 入口） |
| `docs/bugs/<date>-<slug>.md` | 单条记录 |
| `docs/bugs/HOW-TO-USE.md` | 这份文档 |
| `.githooks/commit-msg` | 强制 trailer |
| `supabase/functions/submit-feedback/index.ts` | 反馈接收端 |
| `website/home.jsx` (FeedbackButton, FeedbackModal) | 前端入口 |
| `website/admin.html` (FeedbackTab) | 后台 triage |
| Supabase table `redesign_feedback` | 反馈存储 |

---

## 七、新人 / 新 session 入门

如果你是没有任何此 session 上下文的 Claude，需要修 bug：

1. 打开 `docs/bugs/INDEX.md`，grep 你要碰的代码区域的关键词
2. 命中的话，**先读那份 record 的 Invariant 段**，不要破坏它
3. 改完后，写新的 record（同样 5 段）
4. INDEX 加一行
5. commit 带 `Bug-Record:` trailer
6. 推上去，跑 `republish-bundle` workflow（如果改了网站静态资源）

也看一眼 `docs/gotchas.md` —— 那是没有具体 bug 但值得一读的"silent edge cases"。

修完一类 bug，把发现写进 `docs/gotchas.md` 留给下一位。
