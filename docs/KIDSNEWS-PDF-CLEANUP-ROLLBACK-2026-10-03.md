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

- Python3.10相关套件63项通过；6项新维护测试覆盖PDF、保留原资产、清理/恢复/冲突、归档已写而DB响应丢失后的回滚。
- Oracle真实Supabase演练：latest、日期archive、数据库回滚均通过；模拟首次数据库写成功但响应丢失，同目录恢复未重复写；二次回滚幂等；测试对象删除；现网latest和今日故事/搜索未变。
- 演练私有状态：`/home/opc/.local/state/kidsnews-backups/20261003-maintenance-drill-1/result.json`。
- 18份实际PDF已生成，News Middle四页已逐页视觉检查。当前内容和9篇records不重新生成。

## 当前维护发布

PDF reader SHA256：`8da0d46a5c61f8815bc380c4b88bde455fb7f0dae9d185204110ee81d387ed83`。
修复artifact：`/home/opc/kidsnews/work/2026-10-03/pdf-maintenance-1/reader-artifact`。
按现有artifact分支CI发布→公网核验→finish_publication更新同日归档/DB→先备份再清理75旧对象。
真实发布和清理的最终证据待本轮验收后追加；上述演练并不等于今日现网做过回滚。
