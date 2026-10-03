# 来源前置流水线：最终 Spec / 实现复核

日期：2026-10-02。范围：PR86 共享源码及导出的 Bot PR1，显式 source-first-grok。
用户授权三名子 Agent 分别审查并修复，主 Agent 复核集成与文档。
不调用真实模型、数据库写入、Storage 上传、部署或邮件；不合并生产 main，保留调试缓存。

## 修复与回归

以下新增回归均由对应子 Agent 先复现失败，再验证修复。测试统一 Python 3.10。

| 问题 | 实现位置（pipeline/） | 回归名（省略 test_ 前缀） |
| --- | --- | --- |
| prepare 中断后仍依赖原 registry/连接器，开始时间还会重置 | agent_shadow.py prepare | interrupted_prepare_uses_frozen_context_without_registry_or_connector |
| 历史查重仅看跳转后 URL，原 feed URL 可漏查 | agent_shadow_source_editor.py originals | history_checks_original_feed_and_redirected_evidence_urls |
| 正文缓存哈希未校验，可把被改动证据送入付费写稿 | 同上 | changed_original_body_is_rejected_before_paid_writer |
| 补选缺已 ready 稿的题材/实际出版方，增量规划标题为空 | agent_shadow_batch.py accepted_context/pool；agent_shadow_source_editor.py plan_increment | refill_selector_receives_bounded_accepted_topics_publishers_and_events |
| 增量目录累计超过30；退役条目不能丢失最终搬栏信息 | agent_shadow_source_editor.py plan_increment；agent_shadow.py check_stale | incremental_catalog_stays_bounded_and_retains_retired_routing；stale_review_of_retired_ready_story_uses_final_routed_section |
| 详情首次修复可替换已合格正文和自检，甚至淘汰好稿 | agent_shadow_finish.py finish | first_detail_repair_cannot_replace_passing_body |
| 修 Middle 详情会覆盖已通过 Easy | 同上 | detail_retry_preserves_already_valid_level |
| 详情修复 JSON 无效会误淘汰整篇 | 同上 | detail_syntax_failure_does_not_discard_good_body |
| 已保存空答卷在恢复时因真假值判断被重复请求 | 同上 | resume_empty_pending_answer_never_asks_initial_again |
| 部分详情补修使机械删除关键词的日志丢失 | 同上 | cleanup_removal_is_logged_when_other_level_needs_repair |
| 正式模板 fetch mapper 丢掉 detail_status，隐藏空详情逻辑不生效 | source_first_reader.py adapt_article_shell，适配器v2 | pinned_reader_preserves_omitted_status_in_fetch_mapper |
| 发布恢复只锁定 ZIP，未锁定匹配 manifest | website_release.py LatestRelease._replace | resume_rejects_changed_manifest_before_any_write |
| 回滚仅比较 ZIP，可能覆盖其他写入者的 manifest | website_release.py LatestRelease.rollback | rollback_refuses_foreign_manifest_with_same_zip；partial_rollback_resumes_original_pair_without_reupload |
| 打包证据检查漏标题/卡片，数字硬门禁和引语告警可绕过 | publication_bundle.py build | pack_checks_card_evidence_and_keeps_quote_warnings（数字/引语两种） |

新增文件：test_source_first_review_collection.py（6）、test_source_first_review_finish.py（5）、test_source_first_review_publish.py（6个测试实例），共17个。

## Spec 与运行说明已对齐

- 清理“待实现/仅设计/尚未采用宽字数”等旧草稿描述，统一为当前显式模式。
- 选择阶段传草稿与元数据，精修阶段传该篇原文；补选只带有界的已 ready 稿信息，不重发其完整成品。
- 活跃目录最多30；退役已消费/不合格条目保留审计及最终栏目，不静默删除尚可用备用稿；无法安全缩减则明确停止。
- 正文合格后，详情补修不得修改正文、自检或另一个已合格阅读级别。
- facts_supported=false 与引语逐字不匹配仍仅告警；数字/结构/安全/历史门禁未放宽。
- 本地不足三篇可留结果，正式网站 reader 仍严格三栏各三篇；本次没有扩大部分发布行为。
- reader省略详情必须把标记传到真正页面状态；恢复发布和回滚同时检查 ZIP 与 manifest。

## 验证与剩余事项

共享源码 Python3.10 相关离线测试235项通过（20.63秒）；Bot快照导出后重跑同套测试并在交付及Atlas状态登记。两项既有警告为gotrue弃用和runpy重复模块提示，不是新增失败。
生产 full_round.py、news_rss_core.py 和网站原Action未改。旧包真实发布成功只证明旧链路；本次新模式未运行真实模型、未上线，也未执行真实回滚。
剩余验收：VM 新目录真实生成的选文/正文/详情质量、时间/token，以及批准包的正式模板视觉与实际发布结果。不得把离线通过写成已上线或成本保证。
