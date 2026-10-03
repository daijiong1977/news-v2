# Oct 3 后端核对与 Fun 题材限额

## 数据库（只读核对）

实际查询 information_schema、pg_constraint、当日记录与搜索向量，未改变 schema 或数据。
沿用四表：redesign_runs（运行）、redesign_stories（来源/安全/日期槽位）、
redesign_search_index（easy/middle/zh）、redesign_source_configs（来源轮换）。
没有 article_detail 表，正文与详情沿用 Storage JSON 文件。

Oct 3：News/Science/Fun 各三条 stories，9 个唯一日期槽位；搜索 27 条，
三栏每级各三条，没有孤立搜索记录、空 doc_tsv 或错误的 listing/图片引用。
日期+栏目+slot 唯一约束、run_id 外键、搜索 story_id+level 唯一约束均存在。
复用原槽位 UUID，搜索 zh 对应文件 cn；没有动阅读进度、用户、反馈表。
source_config 六条更新时间已在上一轮读回确认，配置本身不重建。

限制：REST 按行更新，不是跨四表原子事务；运行行的 started_at/finished_at
目前以 packed_at 填写，telemetry 为 archive_backfill/usage_known:false。
它们不能用于推断实际 Codex 用量或耗时，真实时间/用量以运行日志为准。
同日替换复用槽位 ID，读过旧文章的进度仍可能映射新内容，这是现有兼容方案。

## Storage 目录与读取契约（只读核对）

bucket 为 redesign-daily-content：

```text
archive-index.json
2026-10-03.zip
2026-10-03-manifest.json
2026-10-03/
  payloads/articles_{news,science,fun}_{easy,middle,cn}.json  # 9
  article_payloads/payload_2026-10-03-{category}-{slot}/
    easy.json, middle.json                                 # 18
  article_images/{category}-{candidate_id}.webp             # 9 当轮
```

原生产 pack_and_upload 的 dated-flat 与正式 data.jsx / home.jsx 的读取路径一致。
公开 GET 36 个当轮文件全部 200 且 SHA256 与 reader 完全一致。
日期 ZIP SHA256=6920adc539a53886320097bda08e1f1ed772741359bde81fe35ca708479c2dbb，
日期 manifest 与本地相同；archive-index 包含 Oct 3、无重复日期。
SQL 中图片相对路径能由正式模板组成日期 Storage URL。

发现但未删除：Oct 3 日期目录实际 111 个对象（9 listing、54 detail、48 image），
其中 36 个被当轮引用，75 个旧文件未被当轮引用。旧 detail 包含 Apr 24、Sep 20
payload IDs。旧生产 ZIP→dated-flat 会带上历史残留，新的按文件 upsert 也不清旧文件。
因此“本轮读写 38 个对象”不是“整个日期目录只有 38 个对象”。旧文件不参与当前
9 篇的正常加载，清理应另做受引用集合和备份保护的操作，不按整个目录删除。

发现缺口：当前 reader 没有 article_pdfs，正式 article.jsx 的 PDF 下载按钮仍链接
article_pdfs/{story_id}-{easy,middle}.pdf。公开日期 PDF 示例返回 400（未取得 PDF）。
正文、详情、图片正常，不代表 PDF 功能通过。尚未实现 PDF 生成或隐藏该按钮。

四表全量业务 JSON、日期写前备份及 apply/rollback SQL 在 VM 私有 state 目录保留，
不是全数据库备份。未执行真实 rollback，也未修改线上 archive/index/latest。

## 用户最终确认的 Fun 规则

网球最多一篇，游泳最多一篇；允许同时一篇网球和一篇游泳。
不设“所有体育合计只能一篇”。其他体育仍按整体质量、趣味与多样性选择。
同一体育内优先保留 AI 排名更高、质量更好的当前明星稿。

摘要排序、五稿写作和最终 group 提示都明确此规则。新 group request 冻结
fun_topic_limits={tennis:1,swimming:1}，原已冻结/已完成目录不追溯改内容。
Python 按 AI 排名将第二篇同类体育移到备用，提升其他原有五篇候选；
不增加 AI 排序调用、不新增第六篇。已 ready 一篇网球后，后续备用网球不会送精修；
游泳仍可送精修。磁盘交接路径检查最终前三篇限额。
若五篇中确实凑不出满足限额的三篇，保留状态并报告，不改标签或编造候选。
新规则未重新发布今日网站；今日两篇网球仍保持原内容。

## Linux 模型核对

Codex CLI 0.160.0。run 配置 agent_provider={type:codex,reasoning:low}，没有 model。
适配器显式 --ignore-user-config，不使用用户 config.toml 中模型名；未传 --model。
22 个缓存答卷均记录 cli-default (not reported)。只能确认使用 Codex CLI 的默认模型
和 low 推理，无法追认具体型号。没有调用 Grok、DeepSeek 或 Claude。
以后如需要型号可追踪，应在新目录显式设置 agent_provider.model，不修改旧冻结目录。

## 范围与验证

回归涵盖两篇网球拒绝、网球+游泳允许、游泳自己的限额、纯非体育不变、
API 自动提位与恢复零调用、备用跳过重复体育、磁盘导入拦截、旧冻结规则保留。
Python 3.10 离线验证，无真实模型/发布/数据库写。共享源码 PR86，运行快照 PR1。
数据库与归档检查结论来自实际只读查询，不以离线测试代替真实读取。
共享源码相关完整影子/后端套件 373 项通过（两个既有警告），针对性 74 项通过。
