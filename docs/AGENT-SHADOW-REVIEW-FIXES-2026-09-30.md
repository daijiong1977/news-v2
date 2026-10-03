# 2026-09-30 原生 Agent 影子审查修复记录

对应 news-v2 PR #86 与 grokbot-kidsnews PR #1。共享源码先修，运行快照最后导出。
不合并、不推 main，不调用真实模型、数据库写、Vercel 或邮件。
生产 `full_round.py`、`news_rss_core.py`、provider transport 本轮均未修改；影子代码仅复用纯函数。
根目录 requirements 按用户要求与 pipeline 的锁定版本相同，新增 tzdata；两份均保留生产
PDF 所需 fpdf2==2.8.4，防止锁文件同步时丢失生产依赖。

## 回归与改动

| 项 | 位置 | 回归测试（pipeline/test_agent_shadow_review_fixes.py） |
|---|---|---|
| H1 局部补稿 | agent_shadow_editor.edit；backfill.targets / editor-state | test_h1_science_refill_does_not_touch_news_and_preserves_accepted |
| H2 改写修正耗尽换备用、详情降级、关键答卷仍致命 | agent_shadow.ask / AnswerRejected；editor.edit；details.normalize_keywords / enrich_and_review | test_h2_rewrite_invalid_uses_reserve_and_reports；test_h2_real_bad_wordcount_twice_becomes_rewrite_invalid；test_h2_details_bad_keywords_are_filtered_and_invalid_extras_omitted；test_h2_keyword_normalization_drops_only_misaligned_terms；test_h2_essential_rank_and_pick_remain_fatal |
| H3 原子状态和目录锁 | agent_shadow.write / run_lock / main | test_h3_write_is_atomic_when_replace_fails；test_h3_second_cli_step_exits_one_with_json |
| M3 历史不缺失、不静默为零 | agent_shadow.prepare；SKILL 查询说明 | test_m3_registry_missing_or_zero_history_rejected；test_m3_cached_empty_history_cannot_bypass_prepare |
| M4 发布先记尝试、明确失败才重试、零篇不发 | agent_shadow_publish.publish / verify；CLI retry flag | test_m4_timeout_marks_attempt_before_call_and_blocks_blind_retry；test_m4_inconclusive_verify_does_not_allow_retry；test_m4_zero_articles_cannot_publish |
| M5 完成答卷不可改 | agent_shadow.pin_task_answers / verify_answer_hashes | test_m5_real_handoff_cli_and_changed_completed_answer_rejected |
| 小项：时区 / 依赖 / VM 解释器 | main try 中 ZoneInfo；两个 requirements；SKILL | test_small_timezone_error_is_json_exit_one；test_small_locked_requirements_and_vm_runbook |
| M1 原文观点、可空背景、按字段/题审核 | agent_shadow_details 的提示覆盖、validate_details / validate_detail_review / apply_detail_review | test_m1_empty_source_only_extras_and_field_quiz_review |
| M2 新会话第二遍审核规范 | SKILL / instructions；两个 review 请求；review-results.review_method | test_m2_review_session_policy_in_both_runbooks；完整测试确认审稿输入不含写手自评 |

Bot README 的 clone 必须带 `-b codex/stepwise-full-shadow`。修改前 Python 3.10 断言失败
（README clones old main instead of runtime branch），修改后同一断言通过。

## 先红后绿的实测

- 新增首批 15 个回归参数例，在修复前全部失败。
- H1 再单独隔离详情阶段复现：仅 Science 缺第二出版方，旧流程仍额外抓 News 第 13–18 篇。
  修复后 News 仅首批 12 篇各抓一次、只存在原 pick-News 请求且哈希不变；Science 自行补到 NASA。
- 缓存空历史补充案例修复前 `DID NOT RAISE`，修复后拒绝恢复。
- 同一 Python 3.10.20 环境，修复后下列命令 **109 passed**；唯一 warning 为
  Supabase 依赖 gotrue 的弃用提示，不是测试失败。
- 防漏 fpdf2 依赖的断言也先失败，再补回两份锁文件后通过；生产 PDF 模块在 3.10 可导入。
- 完整模拟每栏 24 篇候选，涵盖安全淘汰后备用、News 重要稿、Science 两出版方；
  首批 12 / 后续每批 6；假 fetch 写 WebP 字节，verify 对列表、详情、图片共 36 文件重算 hash。
- 真实 AgentFilesProvider 子进程测试（非 mocked ask）验证退出 2 → 写答卷 → 退出 0，
  每次 stdout 单行 JSON；改完成答卷的空白也退出 1。另测试真实文件字数答卷连续两次无效。

```sh
uv venv -p 3.10 /tmp/kidsnews-review-310.oAQxH8/py310
VIRTUAL_ENV=/tmp/kidsnews-review-310.oAQxH8/py310 uv pip install -r pipeline/requirements.txt pytest
/tmp/kidsnews-review-310.oAQxH8/py310/bin/python -m pytest -q -p no:cacheprovider \
  pipeline/test_agent_shadow_review_fixes.py pipeline/test_agent_shadow.py \
  pipeline/test_agent_shadow_publish.py pipeline/test_shadow_site.py pipeline/test_ai_providers.py \
  pipeline/test_safety_quality.py pipeline/test_quality_rca.py pipeline/test_wc_repair.py \
  pipeline/test_cadence_calibrate.py
```

## 仍需首测确认与保留限制

1. 用户为既有 PAT 勾选新仓库；VM clone、Python 3.10 环境、真实 Grok 答卷、日志推送待验证。
2. 平台必须支持并实际采用新会话/子 Agent 审稿。文件输入隔离不能证明真实会话隔离；
   无法隔离则暂停真实首测，不能声称有独立模型审核。
3. Supabase 连接器只读历史查询、真实内容质量、逐题语义正确性尚无实测；不能拿假答卷证明。
4. VM → Mac 的文件下载见完整流程文档的明确目录清单和 manifest 对照；真实下载未验证。
   不通过 logs 分支传图片/HTML，不往 VM 放部署密钥；下载不完整不得部署。
5. 临时原文/图片抓取失败仍在本轮缓存（未修：避免自动重抓破坏固定输入与审稿对应关系；
   首测可用新 run-dir 重试）。未新增 CI（本次离线 Python 3.10 覆盖已完成；自动化另行接入）。
6. 旧全局 backfill 格式不自动迁移：显式要求新 run-dir，避免把旧审稿上下文混入新流程。

不得把代码 push、Atlas 本机报告成功或假部署测试说成真实 Bot 内容或网站上线。
