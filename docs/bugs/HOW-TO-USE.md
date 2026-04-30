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

## 六、Quality Digest 邮件 + 一键修复（macOS Shortcut）

每天 pipeline 跑完 1 小时后，`self@daijiong.com` 会收到一封 quality digest 邮件，主题形如：

> 📊 Kids News quality — 2026-04-29 ET (last 3d) · 3 pending fixes

如果有 pending item，邮件顶部会有一块橙色面板：
- 列出每条问题（story id + level + 类型 + 之前尝试次数）
- 一个 **🛠️ Drain queue now** 按钮（紫色大按钮）
- 一段 fallback 命令，复制到 Terminal 也能跑

按钮的链接是 `shortcuts://run-shortcut?name=Drain%20Kidsnews%20Queue` —— 这需要你在 Mac 上**装一次**对应的 macOS Shortcut。下面是完整的安装步骤。

### 6.1 一次性安装 Shortcut（5 分钟）

1. 打开 macOS **Shortcuts.app**（Spotlight 搜 "Shortcuts"）
2. 点左上角的 `+` 按钮新建一个 Shortcut
3. 给它起名字 **`Drain Kidsnews Queue`**（**必须**完全是这个名字，包括空格——邮件里的 URL 写死了）
4. 在右侧 actions 搜索栏搜 **"Run Shell Script"**，把它拖到主区
5. 在那个 action 里粘贴这段（注意把 `Shell` 设为 `bash`，`Pass Input` 设为 `to stdin` 或 `as arguments`，都行）：

   ```bash
   bash $HOME/myprojects/news-v2/scripts/drain-autofix-queue.sh
   ```

6. 在右侧 inspector 里勾上：
   - **"Use as Quick Action"**（让它能从 URL 启动）
   - 关闭 **"Show in Share Sheet"**（不需要）
7. ⌘S 保存

测试：
```bash
# 在 Terminal 运行（应该弹出 Shortcuts 跑这个 shortcut）：
open "shortcuts://run-shortcut?name=Drain%20Kidsnews%20Queue"
```

或者点邮件里的"🛠️ Drain queue now"按钮（如果你已经收到过 digest）。

### 6.2 Shortcut 跑起来会发生什么

1. Shortcuts 调 `~/myprojects/news-v2/scripts/drain-autofix-queue.sh`
2. 脚本 source 你的 `.env`（取 SUPABASE_URL / KEY / DEEPSEEK_API_KEY）
3. 脚本调 `python3 -m pipeline.autofix_consumer`（**不带 --once**，把整个队列 drain 完）
4. 每个 queued item → spawn 一个 `claude -p` agent，2-3 分钟一个
5. 跑完弹一个 macOS notification "Autofix drain complete"
6. 日志 in `~/Library/Logs/kidsnews-autofix/$(date -u +%Y-%m-%d).log`
7. 单条 agent log in 同一目录的 `item-<N>.log`

### 6.3 重要提醒

⚠️ **drain 期间不要用 Claude IDE**——每个 `claude -p` 用你 Pro 账号 token，会跟你的 IDE 抢配额。所以建议：
- 早上看 digest 邮件，但**别立刻按按钮**
- 等到午饭、出门、下班前再按
- drain 一次大概是 N items × 3 分钟（队列里 3 个就 9 分钟）
- 跑的过程中你 IDE 会偶尔卡，不要重启 daemon，等 notification 弹出再用

如果你想完全在云端跑（你账号不参与）：本来还有个**选项 C**（GitHub Actions + 单独 Anthropic API key），需要再申请一个 API key 单独计费。要切到那个再告诉我。

### 6.4 自动 daemon 已经卸载

之前我们装的 launchd 自动每 8h tick 已经卸了（`launchctl bootout gui/$UID/com.daedal.kidsnews-autofix`）。现在**所有 autofix 都靠你按按钮**，主动权全在你这边。

要恢复自动 daemon（不推荐，会再次和 IDE 抢 token）：
```bash
~/myprojects/news-v2/scripts/install-autofix-daemon.sh
```

---

## 七、文件位置参考

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
| `pipeline/quality_digest.py` | 每天 quality 邮件渲染 + 发送 |
| `pipeline/quality_autofix.py` | 机械修复（trim）+ 队列入库 |
| `pipeline/autofix_consumer.py` | 队列消费者，spawn `claude -p` |
| `scripts/drain-autofix-queue.sh` | Shortcut 调用的 drain 脚本 |
| `scripts/install-autofix-daemon.sh` | 装 launchd 自动 tick（默认不装） |
| Supabase table `redesign_autofix_queue` | 复杂修复任务队列 |

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
