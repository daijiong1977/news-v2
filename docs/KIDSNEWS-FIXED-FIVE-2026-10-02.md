# Kids News 固定五选三：当前执行 Spec

日期：2026-10-02。当前新轮使用 `source-first-deepseek`，旧目录沿冻结 profile 恢复。
最新执行接口见 `KIDSNEWS-THREE-STAGES-2026-10-02.md`：prepare一次输出15稿；
Grok连续写3份selection和9份成品文件；finalize统一校验并打包/交CI。
下文第二部分的编辑标准保留，但旧“每题后跑Python”交接方式仅用于旧目录。
本文取代旧 source-first-grok 的规划、补稿和调用分工；旧模式不追溯修改。
源码 news-v2 的 PR86，运行快照 grokbot-kidsnews 的 PR1；不 merge main。

2026-10-03 时效更新（新目录）：Python采集最先检查三天美东日历窗口。
Feed日期/URL日期可确认超过三天时不抓正文；抓到正文后再核对网页原始
datePublished（不是dateModified）以及明确以 `On Month D, YYYY` 开头的事件。
例如10月3日的9月30日稿可入，但正文明确讲9月12日活动则淘汰，尚未抓图或调用AI。
日期未知且正文开头也无法确认日期则跳过，未来发布日期跳过；背景历史年份不全局拦截。
隐含/相对/后段事件日期不声称Python能全面识别。News/Science/Fun相同窗口。
不因此自动删除现网、数据库或archive；旧已冻结journal恢复旧政策。
完整规则见 `docs/bugs/2026-10-03-three-day-source-freshness.md`。

## 三大部分

### 一、Python 连续准备＋DeepSeek，输出15篇

1. Python读取当天来源和真实七天历史；文章数据库只读。已核验网站 ledger 覆盖对应日期历史，未发布影子稿不进历史。缺 history 或三栏历史全零停止，不能假装无重复。
2. Python冻结来源、日期、配置、预算。新目录冻结 selection_policy=twelve-five-three-v1；沿原 cadence/priority/主备用顺序，Science 同出版方 feed 本地分组、轮询只是优先顺序。每栏首批目标至少12篇机械合格，不要求三个不同来源或出版方；同来源、同学科完全允许。不足进入下一配置源。这是入口采集，不是五稿之后后补。旧目录沿冻结目标恢复。
3. 每源先检查前6篇，合格第4篇立即停止；不足4再3、再3，总计最多12。首6篇全部失败，本轮 suspend 当前 feed 并换下一源。正文/图片逐篇保存，恢复不重新抓已尝试 URL。
4. 全文与原图由 Python 一起取得，不用AI抓网页。入口原文180–1500词；最终栏目 News350–1200、Science350–1500、Fun180–1200。最终压缩WebP至少20,000字节；小图整篇退出，不找替代图。URL/完全相同标题、feed时效、明显消费导流、实际正文、资源/hash等机械过滤先做。NPR只接真正文字报道，不转写音视频/逐字稿；原生产待办保留，不改生产路径。
5. DeepSeek Pro仅接收候选编号/摘要，abstract为限长标题＋摘要，不传全文，两种模型均关闭thinking。历史只传该栏标题/摘要。候选可以来自其他原始栏目，以支持动物趣事搬Fun、研究留Science、公共事务科技留News、趣味科技留Fun；最终栏目词数/URL历史由Python再次筛。按最好到备用返回5–8个不同合格事件；同来源、同学科、相近题材不作为排除理由。编号映射、topic、importance、initial_risk、history_status/confidence、event_key由Python检查。历史 uncertain 不当clear；风险<4、clear且confidence>=0.7。News重要性优先。如果实际不足5个不同适龄事件，只补采该栏目下一配置源，保存缓存并重排该栏；已完成栏目不重跑。冻结合规来源耗尽仍不足时保存缺口，不虚构ID/重复事件；这不是JSON格式问题。
6. Python按ID取已经缓存的全文和图片，不再打开原网页。DeepSeek每栏一次八选五并写5篇、按偏好排序，含理由与Easy/Middle英文标题/正文/卡片摘要、中文标题/摘要，无详情。Python审查单篇字段/长度/英文/数字/引语等，问题写进python_audit交Grok；单篇缺陷不重新生成整个5篇。五稿不足时明确停止，不假称15稿已完成。

`pipeline.agent_shadow preflight` 连续完成以上步骤，不在便宜的Python边界等待Bot。
输出 `drafts-for-grok.json`：每栏5篇，共15篇，仍为drafts而非ready。
每栏原始答卷及全文保存在 `raw-batch-<栏目>-8.json`；三次短名单也持久保存。

### 二、Grok 固定五选三＋逐篇成品，Python校验

- Grok必须在每栏固定5篇中完成最好的3篇；不能发现新来源、后补第六篇或重写整组。DeepSeek顺序/Python审查是参考，最终三篇由Grok判断，不由Python默默按配额换位。
- 每栏一次组任务返回全部5个ID顺序：3个优先、2个备用。第一轮尽量选质量和组合更好的；优先三篇有稿修不好时进入后两篇，放宽来源/学科/评分等软偏好。News首篇尽量是最重要适龄稿；Science区分physics/chemistry_materials/astronomy/biology并兼顾第二出版方；Fun优先真正趣味、当前精彩游泳/网球明星，而不是仅因退役催泪就压过赛事。均为软偏好，不能因此不完成3篇。
- 每篇一个Grok任务：按原文修正文、归因、引语、限定语、中立性和适龄表达；**同一答卷**生成Easy/Middle详情并自检，接Python校验。一篇ready或转备用之后才开始下一篇，不单独生成/审核详情。
- 不适龄细节删除，保留安全核心。短稿可增加准确、清楚标注的通用名词解释；不能编造新闻数字、日期、角色、事件因果、引语或无来源的另一方观点。背景/观点允许为空。题目必须依据对应级别最终正文回答，避免最长选项泄露答案；Python确定性洗牌。
- Python检查结构、正文与中文字数、英文、关键词是否在本级正文、答案索引、图片/hash；自检分数安全门禁沿分维度3/4（不是统一2分）：sexual/substance/language>=3，violence/fear/distress/adult_themes>=4，bias News>=3/其他>=4。模型只给分，Python决定。
- `facts_supported=false`及引语逐字不匹配只记录告警，不阻止发布；不等于事实被证明。明确不存在的事件数字、最终不适龄内容、历史重复和坏结构仍不能冒充合格稿。
- 正文一次定点修正；详情问题允许额外一次，只修失败字段，不改已通过正文/另一通过级别。坏可选字段先删，仍有坏必填模块则省略该级详情、保留正文。正式reader隐藏省略详情标签。
- 已通过3篇就停止，不因出版方/重要性偏好追第四篇。不足3篇时仅允许修当前5篇；**不得自动后补，也不得发布不足3篇**。若有限修正用尽，保存group-blocked和所有证据，报告具体失败，由维护者修同组恢复机制/规则后继续；计数目标不能伪造安全或成功标记。

正常基线：DeepSeek3次ID摘要排序＋3次批量正文；入口短名单补采/重排、修正/传输重试另计。Grok连续产出3份selection和9份逐篇成品文件。固定五篇的目标是完成三篇，来源和学科可全部相同；同一事件、同一研究/发现以及同栏七天历史重复仍排除。没有独立审核，不凭文件数估算token或保证周额度。

### 三、Python正式模板打包＋现有GitHub发布

- 三栏各3篇ready后生成pack；`publication_bundle build/check`生成私有publication.zip，包含记录/审计，不把内部文件放公开reader。
- `website_release build/check`使用仓库内按**完整commit和逐文件hash锁定**的正式reader-shell，含所有.jsx依赖；绝不从落后本地网站checkout复制。输出reader.zip/latest-manifest.json/records.json。
- `kidsnews_bot --publish --ack-same-day-replacement --branch codex/website-release-…`把这三份文件及hash绑定approval推Bot独立发布分支。Python在push前保存attempting，成功后保存pushed；不确定时不盲重复提交，保留worktree和回执。
- Bot `publish-reader.yml`负责备份当前完整latest对并上传CI artifact，换latest.zip和latest-manifest.json，等读回最多75秒（仅重试GET），dispatch**原kidsnews-v2 Action**，等待公网所有文件hash吻合后记网站有效历史。原网站Action不改。
- Push成功只叫`ci_verification_pending`，不是上线成功。失败保留original CI backup/state；明确resume使用原backup_run_id，不whole-job rerun重备份半写对象。rollback恢复原备份对，不覆盖其他写入者。
- 不写文章/详情/来源数据库，不写日期archive，不调用新增Edge consumer，不发邮件。只更新网站latest所需Storage和私有已核验网站ledger。
- 保留缓存和调试文件。日志包含阶段耗时、调用usage、删减/降级、来源/topic/important；原生token未知写未知。

## 实现映射与验收

| 部分 | 实现 |
| --- | --- |
| 连续Python入口与部署交接 | pipeline/kidsnews_bot.py |
| 来源全文/图片/分组 | pipeline/agent_shadow_source_first.py |
| ID摘要前8与15稿审查 | pipeline/agent_shadow_shortlist.py |
| 固定5篇、Grok组排序、冻结原始批次 | pipeline/agent_shadow_batch.py |
| 逐篇成品、自检、有限修复、无后补 | pipeline/agent_shadow_finish.py |
| HTTP rank/write 与原生editor/review | config/shadow-source-first-deepseek.json；pipeline/agent_shadow_providers.py |
| 私有包/正式reader/备份发布恢复 | pipeline/publication_bundle.py；website_release.py；website_delivery.py；agent/github/publish-reader.yml |
| 新回归与旧模式兼容 | pipeline/test_source_first_deepseek.py；原shadow/website套件 |

离线模拟证明顺序、固定成员、恢复与CI交接，不证明真实稿件质量、模型账单、Storage写入或新站部署成功。真实全轮由用户在VM触发；上线以CI公开hash验证为准。
