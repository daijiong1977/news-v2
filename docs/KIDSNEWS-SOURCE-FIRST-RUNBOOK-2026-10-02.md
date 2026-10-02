# 来源前置混合流水线：新轮与恢复

本指南仅供显式 source-first-grok 新轮；生产 main、DB、archive、邮件不变。
完整规则：KIDSNEWS-SOURCE-FIRST-2026-10-01.md。

2026-10-02：`Unsupported quoted sentence` 改为可追踪告警，不挡发布、不据此额外修稿。
保存 evidence_warnings 并在报告中列出；不是事实通过证明。数字/结构/安全仍可阻止发布。

新目录命令（D/RUN 替换为真实美东日期和新运行名，registry 先完成历史overlay）：

```sh
cd /workspace/kidsnews-shadow
git pull --ff-only origin codex/stepwise-full-shadow
.venv/bin/pip install -q -r pipeline/requirements.txt
.venv/bin/python -m pipeline.agent_shadow prepare --date D --editor-mode autonomous --test-profile source-first-grok --registry work/D/RUN/registry.json --run-dir work/D/RUN
.venv/bin/python -m pipeline.agent_shadow step --run-dir work/D/RUN
.venv/bin/python -m pipeline.publication_bundle build --run-dir work/D/RUN --zip work/D/RUN/publication.zip
.venv/bin/python -m pipeline.publication_bundle check --zip work/D/RUN/publication.zip
.venv/bin/python -m pipeline.website_release build --zip work/D/RUN/publication.zip --output-dir work/D/RUN/reader-artifact
.venv/bin/python -m pipeline.website_release check --release-dir work/D/RUN/reader-artifact
```

以上 step 必须按照返回值逐次完成至 pack，不能直接跳过等待任务执行后续命令。

1. VM `/workspace/kidsnews-shadow` 拉取 `codex/stepwise-full-shadow`，安装锁定依赖。保留所有 work 状态/缓存；不在 VM 修改代码。
2. 按现有 registry_snapshot/只读 Supabase 连接器及网站已核验 ledger overlay 流程取得当天 registry：sources 和真实七天 history 缺一不可，不能用全零绕过。key 只在 env，不写文件或日志。
3. 使用全新运行目录，例如 `work/D/source-first-1`，命令沿用旧 runbook 的 prepare，仅将 `--test-profile` 改为 `source-first-grok`；保留 `--editor-mode autonomous`、真实 `--registry` 和所需显式传输兜底选项。执行器必须是 `.venv/bin/python`。
4. 同目录反复执行 `.venv/bin/python -m pipeline.agent_shadow step --run-dir work/D/source-first-1`。exit 0 前进，exit 2 按返回 request/answer 路径完成当前任务并重跑，exit 1 停止报告，不换目录清零预算。超过24小时仅按 --confirm-stale 重查历史后恢复。
5. Grok 任务有 plan、select、review-finish；最后一个是“精修＋两级详情＋自检”一体任务，不额外开详情审核。不得整组重写。正文失败最多定点修一次；详情再修/删除由脚本管理。facts false 告警不是独立审核通过。
6. 完成 pack 后按 publication_bundle build/check，再按现有 website_release build/check 获取固定正式模板 reader。模板依赖包含 JSX；有降级详情时自动适配，未知锚点停止。记录 ZIP hash、数量、来源/学科/重要稿、实际模型调用/token/阶段耗时、删字段及降级原因。
7. 新流程首轮先保留 ZIP 供本机检查。只有用户批准具体 package/reader hash、网站目标和同日覆盖时才按 KIDSNEWS-WEBSITE-RELEASE-2026-10-01.md 的 website_delivery 交付 FOUR 文件到临时发布分支。Actions 负责备份、latest 两对象替换、既有 kidsnews-v2 dispatch 和公网哈希验证；不写 DB/date archive、不发邮件。
8. 如果 latest 读回失败，保留 release.json 和首次备份 artifact。用同一包和原 backup_run_id 走明确 resume；不得 whole-job rerun 重备份半写状态。回滚使用原备份对；不得口头称回滚已验收。日志推送遵循 BOT.md 的私有 logs 分支规则。

部署实证：旧包恢复发布36948143776、网站Action36948187869成功，58文件公开hash一致。新模式离线测试不是已发布证明，真实新轮质量/回滚仍需验收。

最终复核补充（2026-10-02）：

- prepare 中断后重跑相同命令，优先使用已冻结 prepare-context.json，不重新依赖连接器；开始时间不重置，超过24小时仍须重核历史。
- 详情修复只返回脚本要求的失败详情，不能修改已通过正文/自检，也不能覆盖另一已合格阅读级别。坏格式仍走有限补修或详情降级，不把好正文丢掉。
- 只读 status/日志不等于生产发布成功。网站reader仍必须三栏各三篇；缺稿可保留本地结果，不以不完整reader覆盖网站。
- resume 同时锁定 reader.zip 和 latest-manifest.json；不得手改manifest后沿用同一发布状态。rollback遇到不属于原包/备份的manifest会停止，避免覆盖其他写入者。
- 正式模板省略详情适配器为v2，传递detail_status到页面状态；省略详情的稿件只保留阅读，不展示空测验。
