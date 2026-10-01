# Grok复核后续：已核实的四类影子恢复问题

2026-10-01。共享源码先修，Bot快照随后导出。feature PR #86 / Bot PR #1，不合并main。

## 审查意见与处置

| 核实问题 | 实施位置 | 回归 |
|---|---|---|
| 兜底状态落盘后中断会把旧HTTP答卷重标成native | agent_shadow_providers.native_fallback：fallback_pending先落盘；旧答卷归档、移除可重入；完成交接前不升级来源 | test_fallback_crash_never_relabels_old_http_answer（旧状态/新pending两例）、test_fallback_interrupt_during_quarantine_resumes_same_request |
| 四稿只有instructions，没有硬约束 | 原生fallback request消息追加四稿覆盖规则；agent_shadow.ask限制fallback批量最多4，HTTP仍最多5，原request_id不变 | test_native_batch_five_rejected_four_accepted_same_id |
| 跨日历史复核漏discover及归档字段不一致 | check_stale合并input与当前autonomous目录候选/来源，按最终栏目校验；registry_history统一archived及旧is_archived字段 | test_stale_recheck_includes_discovered_ids_and_archive_schema |
| 预算已满导致后部缓存及缓存补稿不可用 | AutonomousEditor.pool只continue未缓存项；两种extend允许符合资格的未消费缓存，不再抓新原文 | test_fetch_cap_skips_uncached_but_keeps_later_cached_original、test_batch_refill_uses_unconsumed_cached_original_at_cap、test_staged_autonomous_extends_to_cached_original_at_cap |

状态：上述四类已在本轮实现；实施提交将在推送后的审查记录中列明。
`pipeline/test_agent_shadow_grok_fixes.py`共8个测试实例，修复前全部失败，修复后全部通过。
兜底故障测试只模拟HTTP和磁盘中断，不调用真实模型。

Grok的另两项建议不能照单实施：

- 每次命令至多三次known-not-executed尝试，已有持久整轮120次上限；禁止第二次同目录
  调用会破坏“修好key/连接后继续”的已确认需求。累计revision上限是后续可选政策，不是无限重试。
- 超24小时恢复仍覆盖冻结目标日，继续排除该日被替换的成稿，不擅自改成查重自己。
  discover候选必须参加新的历史复核，二者并不矛盾。

## 验证与不变边界

Python3.10.20相关suite：227 passed；新增8项先红后绿。
保留两个既有警告：gotrue弃用、runpy预加载。Deno本轮未跑，未改生产Edge/SQL。

```sh
python -m pytest -q pipeline/test_agent_shadow*.py pipeline/test_batch_single_repair.py pipeline/test_publication_bundle.py pipeline/test_shadow_site.py pipeline/test_ai_providers.py pipeline/test_safety_quality.py pipeline/test_quality_rca.py pipeline/test_wc_repair.py pipeline/test_cadence_calibrate.py
```

未改变生产full_round/news_rss_core/wordcount_policy；未调用真实模型、数据库写、部署或邮件。
来源图政策不变；本轮未删除缓存或运行目录，也未消息Bot或在VM操作。
共享文件导出到Bot后逐文件核对和3.10复测，UPSTREAM记录最终共享提交。

P1–P5仍未处理：部分包删除风险、409/ready幂等、旧writer竞态、live schema、部署核验入库依赖。
它们阻塞生产启用；不把这轮离线通过说成VM真实质量/用量或生产上线通过。

下一步由用户在VM拉运行分支，使用新只读七天registry开始影子pack；出现中断用同run-dir恢复。
HTTP fallback只在prepare显式授权时启用，默认关闭。跨24小时须confirm-stale和新的registry。
