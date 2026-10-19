# PDF、日期归档清理与真实回滚验证

2026-10-03。用户要求先解决：75个同日旧资产、18份PDF缺失、真实回滚验证。
不重新生成文章、不调用模型、不改旧生产full_round/news_rss_core、不合并main。

## 实现

- `reader_pdfs.add_reader_pdfs` 复用正式fpdf2模板，依据最终Easy/Middle详情生成18份PDF；固定日期保证相同输入得到同一哈希。正式reader构建和日期归档自动包含PDF。
- `reader_pdfs.augment_artifact` 修复已批准reader，保留所有既有公共文件字节和records，另生成新reader/manifest；不得覆盖原artifact。
- `publication_maintenance.prune_archive` 只枚举指定日期下四个内容目录。先验证当前manifest/ZIP及所有保留资产，再保存每个旧对象的完整字节和SHA256；删除前再核对版本及对象哈希。默认只计划，`execute=True`才删除。未知状态保留计划/日志，同目录恢复。
- `restore_pruned` 使用私有备份恢复已删除对象；日期版本变化或对象被别人改动则拒绝覆盖。恢复后禁止继续旧清理计划。
- `kidsnews_python.finish_publication` 发生异常写`recovery-required.json`，要求同目录续跑或明确回滚，不盲目重新发布。
- `publication_drill` 是显式维护工具，需`--execute`。使用空历史日期1900-01-01、随机`maintenance-tests/rollback-*` Storage前缀，无source_config修改，无网站dispatch。运行前拒绝已有测试日期记录和非空状态目录。

## 回滚范围与限制

网站latest回滚、日期归档回滚、四表业务回滚是三套有备份的恢复操作，不是Supabase跨Storage/Postgres原子事务。源表仍使用旧service-role REST方式；数据库SQL成对生成用于审计，REST逐行读回恢复。网站回滚不会自动宣称数据库也恢复。

后台完整恢复使用`pipeline.kidsnews_python.rollback_publication`；清理恢复使用`restore_pruned`。保留私有状态目录、before文件、apply.sql/rollback.sql和journal；不能删除状态、整轮重新生成或手写替代SQL。
Storage没有跨机器CAS锁；版本/哈希检查能发现冲突，但不能宣称多写入者绝对原子安全。维护时应避开另一发布者，发生冲突立即停。

## 已验证

- Python3.10相关套件64项通过；7项新维护测试覆盖PDF、保留原资产、清理/恢复/冲突、归档已写而DB响应丢失后的回滚及长稿溢出页脚。较长Science稿允许五页，仍为四个学习步骤，不显示“Step 5 of 4”。
- Oracle真实Supabase演练：latest、日期archive、数据库回滚均通过；模拟首次数据库写成功但响应丢失，同目录恢复未重复写；二次回滚幂等；测试对象删除；现网latest和今日故事/搜索未变。
- 演练私有状态：`/home/opc/.local/state/kidsnews-backups/20261003-maintenance-drill-1/result.json`。
- 18份实际PDF已生成，News Middle四页已逐页视觉检查。当前内容和9篇records不重新生成。

## 当前维护发布

PDF reader SHA256：`9dca27dffe9272ee707b74c73b9b9039dd24fc2641a5b3b6671f6d39736b6f43`。
修复artifact：`/home/opc/kidsnews/work/2026-10-03/pdf-maintenance-2/reader-artifact`。
按现有artifact分支CI发布→公网核验→finish_publication更新同日归档/DB→先备份再清理75旧对象。
网站发布CI [37134270185](https://github.com/daijiong1977/grokbot-kidsnews/actions/runs/37134270185) 成功；未修改原网站Action，dispatch运行 [37134316183](https://github.com/daijiong1977/kidsnews-v2/actions/runs/37134316183) 成功。CI公网hash核验通过。后台同日归档/DB已verify完成，私有备份在`/home/opc/.local/state/kidsnews-backups/20261003-pdf-maintenance-2`。
清理已完成：39旧图片+36旧详情JSON=75个对象，仅2026-10-03；当前日期保留54个引用文件（9列表+18详情+9图片+18PDF），剩余未引用对象0。全部旧字节/hash和journal在`/home/opc/.local/state/kidsnews-backups/20261003-unused-archive-cleanup-1`，目录700、备份文件600，可恢复。

最终验收：9 stories、27 search rows；54日期资产hash逐个一致；18份网站PDF全部HTTP200/application/pdf且与ZIP字节一致；日期ZIP/manifest和公开latest一致；1900-01-01测试行0。私有最终报告在`/home/opc/.local/state/kidsnews-backups/20261003-pdf-maintenance-2/final-verification.json`。

共享源码与运行快照各64项相关Python3.10测试通过；Oracle运行仓库已fast-forward至3c4fa7b，使用新PDF逻辑，Oracle相关套件63通过/1个Deno离线SQL探针跳过（真实REST演练已通过）。上述隔离演练并不等于今日现网做过回滚，也不包含Vercel重新部署旧版的演练；现有CI恢复/dispatch路径未修改。

## 本次维护的恢复顺序

保留原CI run 37134270185的`latest-release-state`/`latest-backup-before-upload`（GitHub retention 30天），不要全job重跑刷新旧备份。

1. 若需要恢复被清理的旧资产，先在日期manifest尚为当前维护版本时调用`restore_pruned(cleanup_state, storage)`。换了日期版本后不能强制覆盖，应按保存的计划人工复核。
2. 若需撤销整个后台维护，再用`pipeline.kidsnews_python`的`operation:"rollback"`、`execute:true`、`state_dir:"/home/opc/.local/state/kidsnews-backups/20261003-pdf-maintenance-2"`和原私有env；入口调用`rollback_publication`恢复原DB/归档，不碰网站latest。
3. 若网站也要恢复，现有`website_delivery handoff --operation rollback --backup-run-id 37134270185`使用同一维护artifact、新release分支和`--push`，由既有CI读取原备份、恢复latest、dispatch并公网核验。不能用新备份或新包冒充原备份。

这三项不是一个原子按钮；每项保存尝试/结果和前后hash，未知结果先读回，沿原状态目录恢复。今天仅用户授权的维护修复发布，未启用定时、未修改main。
