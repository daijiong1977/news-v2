# 网站先行发布：实现、CI 设置与 Bot 完整 prompt

## 状态和边界

先改 news-v2 feature PR86，导出 Bot feature PR1；不合并、不改生产流水线或
kidsnews-v2 原 Action。固定正式模板 b9592e0（完整 SHA/22 文件 hash 在 config）。
旧 Action 仍 GET Supabase latest.zip → 解包 site/ → commit → 既有 Vercel 发布。
新 Action 在 Bot repo：`.github/workflows/publish-reader.yml`（共享源 agent/github）。
Bot 推 **公开 reader.zip + 旧格式 manifest + 私有 records + hash 绑定 approval**，
新 Action 才做 Storage latest 两对象/dispatch/公开核验。DB、日期 archive、pending、
Edge Function、邮件、DNS 一律不动。上传本身可能被旧 cron 读走，已经是发布动作。

## 首次 CI 设置（维护者，不是 Bot 临时改权限）

1. grokbot-kidsnews 建立 environment `kidsnews-production`，放两个 secrets：
   SUPABASE_SERVICE_KEY；KIDSNEWS_DISPATCH_TOKEN。不要放 VM、不贴聊天、不放包。
   后者对 kidsnews-v2 Contents write（repository_dispatch）、Actions read；news-v2 Actions read。
2. repository variable `KIDSNEWS_WEBSITE_TRIAL_ENABLED=true` 才允许发布 job；默认不存在则跳过。
   开启表示授权网站试用，包发生改变需重新 handoff；approval 有效期四小时。
   环境如套餐支持 required reviewers，建议设置；未支持时 variable 由维护者控制。
3. VM PAT 必须能向 Bot repo push 新 artifact 分支；涉及新增 workflow 的首次推送可能
   还需 Workflows write。不能让 Bot 为解决 403 自行扩大 token scope。
4. 不需要 workflow_dispatch 登记到 main：新分支 `codex/website-release-*` push
   `releases/current/**` 直接触发其 workflow。代码 PR 推送不会自动发布。
5. 首试安排旧 Daily/republish 与网站同步均已结束的窗口。preflight 拒绝任一目标
   repo 未完成的 workflow，但不是跨仓库分布式锁，仍需人工窗口。

本轮只检查 CI 配置为空，未创建环境/配置秘密/运行真实发布。设置前可以生成预览。

## 可执行命令

先新 registry（只读源配置和同栏目七天历史），再合并已核验网站历史：

```bash
.venv/bin/python -m pipeline.website_ledger snapshot --output work/ledger/effective-publications.json
.venv/bin/python -m pipeline.registry_snapshot --date D --output work/D/RUN/registry.json --env-file .env
.venv/bin/python -m pipeline.website_release overlay --registry work/D/RUN/registry.json --ledger work/ledger/effective-publications.json
.venv/bin/python -m pipeline.agent_shadow prepare --date D --editor-mode autonomous --test-profile batch-grok-details --registry work/D/RUN/registry.json --run-dir work/D/RUN
.venv/bin/python -m pipeline.agent_shadow step --run-dir work/D/RUN
```

若 VM 只读权限由连接器提供而非 SUPABASE_READ_TOKEN，用既有只读连接器生成同 schema
registry，仍须 ledger overlay。不要打印 .env，缺权限停止，不把 history 当空。
exit2 回答指定 request 后同目录继续；exit1 停止；exit0 按 next。

生成完成：

```bash
.venv/bin/python -m pipeline.publication_bundle build --run-dir work/D/RUN --zip work/D/RUN/publication.zip
.venv/bin/python -m pipeline.publication_bundle check --zip work/D/RUN/publication.zip
.venv/bin/python -m pipeline.website_release build --zip work/D/RUN/publication.zip --output-dir work/D/RUN/reader-artifact
.venv/bin/python -m pipeline.website_release check --release-dir work/D/RUN/reader-artifact
.venv/bin/python -m pipeline.website_delivery handoff --artifact-dir work/D/RUN/reader-artifact --branch codex/website-release-D-RUN --push
```

D/RUN 是占位符；分支只用小写字母/数字/连字符。handoff 从当前运行 HEAD 创建
独立 detached worktree，只 stage 四个 artifact 文件；原 VM index/运行状态不动，
拒绝重复远端分支，不 force push、不推任何 main。保留 worktree/调试文件。
只在本轮已授权正式覆盖、CI 已设置、正式模板预览通过后执行 --push。

## Actions 运行与恢复

新 job：验证 secrets/receipt → 恢复历史状态或下载旧 ZIP/manifest →
**先上传 latest-backup-before-upload artifact** → 只替换 latest 两对象 → 双对象读回 →
发 news-v2-uploaded → 最多约15分钟等公开全文件 hash → 写私有有效历史分支。
无论失败/成功，保存 `latest-release-state`（30天）；报告对应 Actions run 链接。
这不是永久备份：试用期间维护者应下载保留；过期前不得依赖其恢复。
同一天 ID 复用会影响阅读进度/搜索/历史语义，approval 显式确认该已知限制。
旧 morning 后续同日重跑可能被 mined_at 门禁拒绝；不自动启用 ALLOW_STALE_UPLOAD。

同一 HTTP 超时：有 attempting 先读远端，匹配才继续；不匹配暂停人工检查。
dispatch 超时为不确定，必须查已有同步 run，脚本不会自动重复通知。
GitHub rerun 从干净 runner 开始，**不要点击整轮 rerun 重新备份覆盖**。
用同一 artifact 新分支 +原 run ID：

```bash
.venv/bin/python -m pipeline.website_delivery handoff --artifact-dir work/D/RUN/reader-artifact --branch codex/website-release-D-resume1 --operation resume --backup-run-id ORIGINAL_RUN_ID --push
.venv/bin/python -m pipeline.website_delivery handoff --artifact-dir work/D/RUN/reader-artifact --branch codex/website-release-D-rollback1 --operation rollback --backup-run-id ORIGINAL_RUN_ID --push
```

resume/rollback 下载原 `latest-release-state`，不会重做生成或替换旧备份；恢复只写
latest 两对象、不删除 DB/archive。损坏备份/其他 writer/历史账本改变则拒绝。
如果 runner 被强杀连最终 state artifact 都没保存，停止并用
latest-backup-before-upload 人工恢复，不宣称此类故障已有无条件一键恢复。
已尝试但未成功的 PUT 不自动重发；明确确认为未执行后需维护者处理状态。
网站同内容无新 commit 正常；真正成功标准是公开文件匹配，不是新 commit 或 dispatch 204。

## 给 Bot 的完整 prompt

```text
在 /workspace/kidsnews-shadow 做一次完整三栏 batch-grok-details 网站试用。
先 git status --short / branch / HEAD；干净且为 codex/stepwise-full-shadow 才
git pull --ff-only origin codex/stepwise-full-shadow 并安装锁定 requirements。
读 AGENTS.md、BOT.md、agent/skills/kidsnews-shadow/SKILL.md 以及
docs/KIDSNEWS-WEBSITE-RELEASE-2026-10-01.md；UPSTREAM 与当前 HEAD 记进报告。
使用美东当日 D、全新 RUN，先取得只读 registry 并 overlay website-effective-history。
按本文件真实命令 prepare/step，一次一个单元。exit2 读 request/写答卷后继续；
不要盲循环，不重写整组，不删已完成答卷/预算，断点恢复必须同目录。
DeepSeek 每栏八选五+正文；Grok 五选三、只修选中稿、一次生成详情并自检。
重要 News 优先、Science 物理/化学等学科多样；Fun 明星游泳/网球同质量优先。
历史去重/安全/有据中立仍优先；图片来源图机械检查，不额外图片模型审核。
完成内部 ZIP build/check，再 website_release build/check，用固定正式 reader 模板，
不上传内部 publication.zip。检查九篇、18详情、图片与摘要，保留调试文件。
已授权本轮网站试用且 CI 配置已由维护者确认后，按 handoff --push 推新
codex/website-release-D-RUN artifact 分支；只推四个 release 文件、不修改代码/main。
等待新 Publish website-only reader 和旧 Sync content from Supabase、真实公开 hash。
若 job skipped 或 secrets/403/审批/冲突阻塞，报告已生成未发布，不绕过权限。
不调用 publication_bundle upload、agent_shadow publish、Edge Function、SQL、日期
archive、邮件、Vercel CLI；不改旧调度。失败停止保存现场，按 runbook 恢复，不重跑模型。
最终报告：ET起止/各阶段时间、候选与8→5→3、DeepSeek每次调用/token/native任务，
来源与重要News、ZIP/SHA、artifact分支/commit、两个Actions链接、备份run ID、
public_verified或明确失败、DB/archive未同步和需要我处理的事项。
```

## 验证与剩余风险

新增13个Py3.10回归覆盖：坏批次不重送、JSX复制、公开包剔除、依赖/哈希拒绝、
latest-only/恢复幂等/超时读回、损坏备份/竞争 writer、历史覆盖、receipt records/hash、
英文CJK/引语/数字证据。数字/引语规则保守，合法单位转换也可能拒绝；遇到时
只报告具体稿，不绕过、不重新生成整组。它不是独立事实审核。
Actionlint 已验；旧 Action 无改动。首次真实 upload/dispatch/公开验证/恢复仍未演练。
浏览器连接当前工具不可用，正式包静态依赖已验，但首页/移动阅读/家长页仍须人工预览。
来源 last-used_at 与旧生产历史、搜索/date archive 不与 Bot 同步：第二阶段再做。
Cloud 再审优先：CI权限/竞争、两对象部分失败、恢复 artifact 丢失、账本与实际站点一致性。
