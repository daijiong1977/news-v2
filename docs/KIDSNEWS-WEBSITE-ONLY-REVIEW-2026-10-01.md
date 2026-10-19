# Kids News 网站先行方案：Spec 与实现审查（2026-10-01）

只读审查 `KIDSNEWS-WEBSITE-ONLY-SPEC-2026-10-01.md` + `RUNBOOK`，按其 §1 顺序对照代码。
未修改代码、未 commit、未调用模型/数据库写/上传/部署/邮件/工作流。

**核对的基线**
- news-v2 `codex/agent-provider-boundary` @ `f4ccbee`（Spec 写 `72b38b2`，之后三个提交只有 docs）；Bot `codex/stepwise-full-shadow` @ `dc3840f`（Spec 写 `8928c0a`，同理）。
- 两仓库 `pipeline/ config/ agent/ supabase/ shadow/` 逐文件相同；`UPSTREAM.json` 指向 `f4ccbee`。两边工作树干净。
- kidsnews-v2：本地 checkout 落后 origin/main **248 个提交**；本文所有网站事实来自 `origin/main` @ `b9592e0`（2026-10-01 10:33Z 的 sync 提交）。
- Python 3.10.20：影子 / 批量 / 恢复 / ZIP 相关 174 项通过。Deno 未跑。
- 上次 REVIEW 的 B1–B7、S7 在代码里都有对应实现和测试（`test_agent_shadow_resume.py`、`test_agent_shadow_grok_fixes.py`）。本文不重审那些；但 B5 的修法引入了一个新的 P0（见 P0-1）。

## 一句话结论

**Spec 的阶段边界和禁止清单是对的、可以保留**；但第一阶段"写 latest 两对象 + dispatch + 回滚"的适配器一行代码都没有，正式模板复制还会把站点打坏，并且 B5 修复带来一个会无限重调 DeepSeek 的回归。当前状态只能做"生成到内部 ZIP"，不能做任何形式的正式网站试用。

---

## P0　阻塞第一阶段上线

### P0-1　批量答卷被拒后，同样 8 篇原文会被反复送给 DeepSeek（B5 修复引入的回归）

- 位置：`pipeline/agent_shadow_batch.py:183-188`（`batch-invalid` 现在写 `considered: []`）、`:238-256`（`extend` 看到这 8 篇仍 available 就返回 `target+8`）。
- 复现（离线，`setup_batch` 基础上让 `rewrite-batch-Fun-*` 永远 `AnswerRejected`，discover 返回空）：
  `rewrite-batch-Fun-8, -16, -24 … -360`，**45 次**同一组 `fun00–fun07` 被重新送出，直到测试 200 步上限；真实环境会一直打到 `MAX_HTTP_CALLS=120`。
- 影响：一次 DeepSeek 内容不合格（修正两次仍错）→ 最多 ~100 次五篇写稿调用，直接违反"绝不整组重新写"。
- 最小修正：`batch-invalid` 时把 8 篇写进 `considered`（恢复旧行为），或者单独记 `rejected_batches` 并在 `extend` 里排除"已被拒过的完全相同候选集合"。同一候选集合最多送一次。
- 验收：`test_rejected_batch_never_resends_same_candidates`（断言 rewrite-batch-Fun 只 1 次，之后进入 discover/告警）。

### P0-2　正式模板复制漏 `.jsx`，部署后整站白屏

- 位置：`pipeline/publication_bundle.py:142`（后缀白名单无 `.jsx`）。
- 事实：kidsnews-v2 `origin/main` 的 `site/index.html` 引用 `article.jsx components.jsx components/Big21.jsx components/SunFace21.jsx data.jsx home.jsx user-panel.jsx`，另有 `parent.jsx`。同步 Action 是 `rm -rf site` 再解包，缺的文件不会从旧站保留。
- Spec §10 已标注；确认属实。修正后仍需浏览器验收（Spec §4 已要求）。
- 验收：`test_shell_copy_includes_every_index_reference`——解析 `index.html`/`parent.html`/`podcast.html` 的 `src/href`，断言每个本地引用都在包内。

### P0-3　公开 reader ZIP / 旧 manifest 生成器不存在

- 现有 `build()` 产出的是内部包：含 `publication-records.json`、`source-usage.json`、`publication-manifest.json`，且 `done.json`/`site/shadow-run.json` 的影子 `app.js/index.html` 会和正式 shell 混在同一个 `files` 字典里（site/ 先放入，shell 后覆盖同名文件，但影子的 `app.js`、`style.css`、`robots.txt`、`vercel.json`、`shadow-run.json` 会留在包里）。
- 位置：`publication_bundle.py:130-144`。
- Spec §4 要求"公开包只含正式 shell 和 reader 数据"；目前无法满足。`latest-manifest.json`（version/packed_at/git_sha/zip_bytes/zip_sha256/story_count/stories）也没有生成器。
- 验收：`test_reader_zip_has_no_internal_or_shadow_files`（断言不含 `publication-records.json`、`source-usage.json`、`shadow-run.json`、`app.js`、`robots.txt`、`vercel.json`、`tasks/`）。

### P0-4　latest-only 上传、备份、批准、dispatch、回滚适配器全部未实现

- `grep latest.zip|latest-manifest|repository_dispatch pipeline/publication_bundle.py pipeline/agent_shadow_publish.py` → 无结果。
- 现有 `publication_bundle upload` 写的是 `kidsnews-publication-pending/pending/`（第二阶段投递）；`agent_shadow publish` 部署独立影子 Vercel。两者都不能顶替，RUNBOOK §3 已明确。
- Spec §6 的 `release.json` 状态机、§7 回滚、§8 账本：均无代码。矩阵标注正确。

### P0-5　执行身份没有着落

- `redesign-daily-content` 的 `latest.zip` / `latest-manifest.json` 由生产 CI 用 `SUPABASE_SERVICE_KEY` 以 `upsert=true` 写入（`pack_and_upload.py:519,530,674,680`）。
- `20261001_bot_publication_handoff.sql` 只给 pending bucket 建了 allow-list 策略；**没有任何策略允许非 service-role 身份写 `redesign-daily-content` 的两个 latest 对象**。
- `repository_dispatch` 需要对 kidsnews-v2 有 `repo` 权限的 token（生产用 `KIDSNEWS_DISPATCH_TOKEN`）；VM 的 PAT 只覆盖 `grokbot-*`。
- 结论：第一阶段要么由持有 service key 的 Mac/CI 执行上传与 dispatch（Bot 只交 ZIP），要么新增一条只允许 `name in ('latest.zip','latest-manifest.json')` 的 storage 策略 + 专用身份。Spec §9 说"需核验"，应改成二选一的明确决定。

---

## P1　第一阶段可控、但多日试用或恢复时会出问题

### P1-1　有效发布账本 / 次日 registry overlay 未实现

- Spec §8；`registry_snapshot.py` 只读 DB。单日试用可人工注明；第二天开始 Bot 不知道昨天自己发了什么，同栏七天查重失效。
- 另外早上生产 `full_round` 也不读账本，会和 Bot 昨日稿撞事件（Spec 已承认）。

### P1-2　回滚依赖的 `restore_latest_from` 不校验、可缺 manifest

- `pack_and_upload.py:662-683`：下载 `<D>.zip` 直接 upsert 到 latest，manifest 缺失就跳过，不比对 hash、不检查 ZIP 结构。
- `D.zip` 是 `upsert=true` 写的，不是不可变（Spec §7 说对了）。若当天早上生产没跑（`D.zip` 不存在）则 restore 报错，必须靠独立备份。
- 建议：第一阶段回滚不要走 `restore_from_date`，直接用适配器从本地独立备份恢复两对象并读回 hash。

### P1-3　同日 slot ID 冲突的用户侧影响

- 列表/详情 ID 是 `D-category-slot`；Bot 包与早上生产包 ID 相同、内容不同。
  - `kidsync.js` 的阅读进度 / picks 以 ID 记录 → 用户早上读过的 `D-news-1` 中午变成另一篇，但显示"已读"。
  - 搜索走 `redesign_archive_search`（DB 索引仍是早上稿）→ 点击今天的结果打开的是 Bot 稿。
  - 归档页 `/archive/D` 读 Storage `D/payloads/`（早上稿），首页读 Bot 稿。
- Spec §2 已列为"必须抽查"。建议升级为：试用期间**不覆盖已被早上生产发布的日期**，改为只在早上生产未跑、或先回滚早上包并清楚告知的窗口试用；或者给 Bot 稿一个不同的 slot 段（4–6）——但那需要前端支持，第二阶段再议。

### P1-4　manifest `mined_at` 与生产的"不覆盖更新内容"门禁

- `pack_and_upload.check_not_overwriting_newer()`（:637-659）比较远端 manifest 里 `stories[].mined_at` 与本地最新值，远端更新则拒绝上传。
- Bot 包 `mined_at` = 打包时刻（中午）→ 同日人工重跑早上生产会被拒（需 `ALLOW_STALE_UPLOAD=1`）。这是**保护**，但要写进 RUNBOOK，否则有人会误以为生产坏了。
- 次日 06:10 生产 `mined_at` 更新 → 正常覆盖 Bot 稿。符合"保留早上旧流程"。

### P1-5　同步 Action 的"无变化跳过"与观察窗口

- Action 只在 `git diff --cached` 有变化时提交；若 Bot ZIP 解包结果与当前 site 完全相同（例如回滚到刚才的包），不会有新提交，也不会触发 Vercel 部署——这是正常的，但 §6 "sync_observed" 不能只等新提交，要以公开文件 hash 为准。
- `republish-bundle.yml` 只等 90 秒看 kidsnews-v2 新提交；Spec/RUNBOOK 已指出不等于 Vercel 完成。

---

## P2　可后续处理

- `publication_bundle.build()` 的 shell 来源是目录而非 commit；本地 `~/myprojects/kidsnews-v2` 落后 248 提交就是反例。实现时用 `git -C kidsnews-v2 archive <sha> site/` 到临时目录。
- 内部 ZIP 的 `publication-manifest.json` 若随 reader ZIP 公开，只泄露文件 hash，可接受，但 Spec §4 应明确是否包含。
- `transport_failure()` 用 `repr(exc)` 里的字符串判断"连接前失败"（`agent_shadow_providers.py:28-31`），依赖 urllib3 的报错文案；可改为检查 `exc.__cause__` 类型。
- `fallback_run()` 的跨目录账本按 `work/D/RUN` 三层目录推断父目录（`:86`），目录结构变化会失效；放到显式路径更稳。
- Spec §3 "原文抓取预算 12 次/栏" 与代码一致（`LIMITS["body_fetches"]=12`，`body_fetches_by_category`）。

---

## Spec 本身：矛盾、遗漏与建议修订

1. **§6 高估了"两个对象非原子"的风险，低估了另一个。** 同步 Action 只读 `latest.zip`，不读 manifest；Supabase 单对象 PUT 是原子替换，并发 GET 得到旧或新完整对象。真正的风险是：(a) Action 的 2 小时 cron 可能在上传后 0–120 分钟内任何时刻把它拉走——即"上传即发布"，批准必须在上传之前而不是之后；(b) `latest.zip` 已换、manifest 未换的间隙只影响生产的 `check_not_overwriting_newer`。建议 §6 改写为"上传 = 不可撤回的发布动作，批准绑定上传前的本地 hash"。
2. **§2 允许 dispatch，但 §9 没决定谁来 dispatch。** 结合 P0-5：建议第一阶段明确"Bot 只产 ZIP，上传/dispatch/回滚由 Mac 维护者用现有 CI 身份执行"，等于把发布权留在人手上，也避免给 VM 新增任何写权限。等稳定后再谈专用身份。
3. **§3.6/§7 "无第三模型审核"用于正式网站。** 影子站可以接受，正式儿童站不该。至少加上次 REVIEW S5 的三条零成本机械校验（引号内句子逐字在原文、英文无 CJK、数字集合 ⊆ 原文数字集合），作为打包前门禁。
4. **§4 "ZIP 根目录必须直接包含正式 shell"** 应明确列出当前 origin/main 的全部 shell 文件清单（含 `admin.html parent.html podcast.html autofix.html kidsync.js assets/ components/ fonts.css tokens.css`），并要求对清单做 hash 固定，而不是"index.html 引用的文件"——`parent.html`/`podcast.html` 也各有引用。
5. **§2 第一阶段禁止项漏了两条：** 不得调用 `agent_shadow publish`（影子 Vercel）把正式包部署到影子站以外的项目；不得用 `--http-fallback native` 以外的方式更换 profile 中途换模型。RUNBOOK §2 末尾提到后者，Spec 应同步。
6. **§8 账本的真正用途**是查重，不是报表。最小实现：`work/ledger/effective-publications.json`，按日期存 `{category: [{title, source_url, topic, event_summary}]}`，仅 `public_verified` 后写，registry 合并时按日期替换 DB 同日集合。比 Spec 描述的"所有者/多 VM"简单得多；多 VM 并行本就不应在第一阶段出现。
7. **§1 基线 SHA 已过时**（docs 提交之后）；下次改成"以 UPSTREAM.json 为准"。
8. **§11 验收清单**应加 P0-1 的"同一候选集合最多送一次"和 P1-3 的"不覆盖已发布日期"检查。

---

## Spec ↔ Code 矩阵（本次核对）

| 要求 | 文件/证据 | 状态 |
|---|---|---|
| 8→5→3、单篇修稿/备用 | `agent_shadow_batch.py`、`agent_shadow_editor.py` | 已实现；**P0-1 回归**（batch-invalid 重送） |
| 缺重要 News/第二出版方只在有可能改善时补 | `agent_shadow_editor.py` `needs()` | 已实现（B4） |
| 每栏抓取预算 12 | `agent_shadow_autonomous.py:18,192-194` | 已实现 |
| HTTP 失败分类、answer 即提交记录、重试、兜底 | `agent_shadow_providers.py` | 已实现（B1/B2/S7），174 项通过；真实 DeepSeek 失败未演练 |
| 24h stale 续跑 | `agent_shadow.py:120-122` | 已实现（B3） |
| 原生详情一次生成自检 | `agent_shadow_details.py:142-`、`config/shadow-batch-grok-details.json` | 已实现；非独立审稿 |
| 来源图机械检查 | `agent_shadow_batch.py` pool / `agent_shadow_details.py images` | 已实现；非视觉批准 |
| 正式模板复制 | `publication_bundle.py:136-144` | **缺 .jsx（P0-2）**，来源应为固定 commit |
| 公开 reader ZIP + 旧 manifest | 无 | **未实现（P0-3）** |
| latest-only 上传/备份/批准/状态机 | 无 | **未实现（P0-4）** |
| dispatch / 回滚 / 公开核验接入 | 无；`verify_site` 可复用 | **未实现（P0-4）** |
| 执行身份与 Storage 策略 | 迁移只覆盖 pending bucket | **未决定（P0-5）** |
| 有效发布账本 / overlay | 无 | 未实现（P1-1） |
| 旧 writer 协调 | 06:10 ET daily（kidsnews-v2 每日 ~10:33Z sync 提交为证）、quality-digest 只写 `D/` 归档不写 latest、republish-bundle 手动 | 需人工窗口；autofix **不**碰 latest（比 Spec 描述乐观一点） |
| DB/archive 同步 P1–P5 | finalize-news-publication 等 | 第二阶段，保持停用 ✓ |

## 结论

- **现在能做的**：VM 上跑 `batch-grok-details` 到内部 `publication.zip`，人工看质量。这一步值得先做，和适配器开发并行。
- **进入正式网站试用前必须完成**：P0-1（先修，一行回退即可）、P0-2、P0-3、P0-4、P0-5 的决定。建议 P0-5 直接定为"人在 Mac 上传"，适配器就只需要：从内部 ZIP 转 reader ZIP + manifest → 本地独立备份当前远端两对象 → 写两对象并读回 hash → 等 cron 或手动 dispatch → 公开逐文件比对 → 写 `release.json`。
- **第一次真实试用建议**：选一个早上生产没有发布、或明确先回滚早上包的日期，避开 P1-3 的同 ID 冲突；回滚演练在正式试用之前单独做一次。

## 维护者修复记录（2026-10-01，原审查正文保留）

代码提交以 Bot UPSTREAM.json 和 PR86/PR1 实际 HEAD 为准。

| 项目 | 修复/决定 | 验证与剩余 |
|---|---|---|
| P0-1 | rejected batch consumed=本组全部候选；有效未选候选仍保留 | test_rejected_batch_never_resends_same_candidates；已先失败后通过 |
| P0-2 | JSX复制；固定网站b9592e0全22文件，hash pin | test_shell_copy_includes_every_index_reference；真实旧ZIP已转换；浏览器视觉待验 |
| P0-3 | website_release build/check清洁reader+旧manifest | 无内部材料/缺依赖/改hash拒发测试 |
| P0-4 | 最新两对象独立备份、原子状态/锁、超时读回、dispatch、全公开hash、原run artifact恢复 | fake tests通过；Actionlint通过；真实CI与恢复未演练 |
| P0-5 | 选择Bot GitHub Action持钥，VM只推artifact；不改Storage策略 | secrets/environment当前为空，真实发布阻塞直到维护者配置 |
| P1-1 | 私有website-effective-history分支，公开核验后更新；新registry显式overlay | 七日/同日排除测试；旧生产和来源last-used仍不读新账本 |
| P1-2 | 新恢复仅独立ZIP/manifest验证备份；不走旧restore_latest_from | 损坏备份拒绝测试；旧生产函数不改 |
| P1-3 | approval显式ack same-day slot风险；不承诺无用户阅读影响 | 新试用需人工抽查阅读/搜索/date archive；后台同步延后 |
| P1-4 | runbook明确mined_at旧重跑门禁，不自动绕过 | next-day旧生产维持原行为 |
| Spec建议 | 固定CI身份/全模板/私有ledger、上传即发布、禁错入口；英文CJK/引语/数字机械门禁 | 13新回归；无额外模型；数字转换等保守false positive需人工处理 |

完整执行与Bot prompt：KIDSNEWS-WEBSITE-RELEASE-2026-10-01.md。
250项Python3.10离线通过不是正式上线。DB/archive/P1–P5仍按第二阶段禁止。
无跨repo分布式writer锁；CI serialized只管新job，必须选择无竞争窗口。
如果runner强杀后最终state artifact缺失，用before-upload独立备份人工处理，
不能盲点rerun重新备份，亦不能声称所有故障无条件一键恢复。
