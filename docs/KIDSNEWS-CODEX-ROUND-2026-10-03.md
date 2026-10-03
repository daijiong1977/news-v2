# Oracle 全 Codex 实验

仅显式 `agent_provider.type=codex`、`all_ai=true` 开启。默认 Pro/Flash/Cursor
行为保持不变；不改变生产 full_round/news_rss_core 或现有网站 Action。

Python 读取冻结的源/七天历史，先抓正文图片、机械过滤，再交 Codex 做摘要
排序和每栏五稿。Codex 对固定五篇排序，逐篇精修、生成 Easy/Middle 详情并
自检，Python 校验直到每栏三篇。所有模型调用由 CLI 的独立临时空目录运行，
stdin 输入，JSON 答卷输出，read-only/never/ephemeral，禁工具、不传数据库
或 GitHub 密钥。CLI 未报告模型名时注明未知，不猜测默认型号或订阅费用。

示例配置（私有文件，路径替换为运行机实际路径）：

```json
{"operation":"run","date":"2026-10-03","run_dir":"/home/opc/kidsnews/work/2026-10-03/codex-1",
 "agent_provider":{"type":"codex","reasoning":"low"},"all_ai":true,
 "env_file":"/home/opc/vocab-agent/.env","execute":true,"publish":true,
 "ack_same_day_replacement":true,"branch":"codex/website-release-20261003-codex-1",
 "database_archive":true,"database_transport":"rest",
 "state_dir":"/home/opc/.local/state/kidsnews-backups/20261003-codex-1"}
```

运行 `.venv/bin/python -m pipeline.kidsnews_python --input-file <私有配置>`。
同目录恢复；不得删除 attempting、答卷或备份。未知模型结果不自动重发。
排序/改写答卷的校验错误最多一次修正，保留原始缓存答卷。

发布 reader.zip 走既有 GitHub Action，检查网站逐文件哈希后，Python 先保存
日期 archive 和四表 before-image、自动 apply.sql/rollback.sql，再更新 archive、
数据库并读回验收。使用已有 service-role Data API，REST 四表不是整体事务；
避开其他写入者，检测到竞争即停止。状态/SQL备份在私有仓库外，不进 logs。

同一 Codex 写稿并自检不是独立审核。正常不调用 DeepSeek、Grok、Claude，
也不需要 Grokbot 云端。仅仓库历史名称保留。真实发布结果另记运行报告。
