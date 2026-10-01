# Kids News：DeepSeek 正文 + Grok 最终详情

2026-10-01。仅影子 feature PR #86 / Bot PR #1；生产未更改。新模式
`--editor-mode autonomous --test-profile batch-grok-details`；旧模式与已冻结运行保持不变。

## 从实验到本次决定

最早全原生逐篇写稿、审稿和详情消耗用户约 7% 周配额；之后改成 DeepSeek 负责
批量正文、Grok 选稿和定点修稿。2026-10-01 三栏影子测试各三篇完成 ZIP，用户观察
Grok 约 3% 周配额。配额是用户观察，日志没有 Grok token/账单，不能转换为费用保证。

从私有 logs 分支独立读取 batch-quality-1：99 条摘要（46/18/35），历史每栏21条；
实际原文抓取8/11/8次，Science包含失败或不合格抓取；草稿各5，最终各3，无补稿。
DeepSeek 21次不是21次写稿：

| 任务 | 调用 | 输入 token | 输出 token | 合计 | API 记录秒数合计 |
|---|---:|---:|---:|---:|---:|
| 八选五并写正文 | 3 | 50,597 | 16,630 | 67,227 | 83.710 |
| 详情生成 | 9 | 33,058 | 20,365 | 53,423 | 93.194 |
| 详情字段/题目审核 | 9 | 38,224 | 1,080 | 39,304 | 12.446 |
| 总计 | 21 | 121,879 | 38,075 | 159,954 | 189.350 |

原生15任务＝计划1、选三3、修稿9、格式修复2；原生交接总871.309秒，包含等待，
不是纯模型推理时间。metrics到done为26分27.334秒；用户报告含准备约28分钟。
详情及其审核消耗92,727 token（约58%）。三增强字段被删除、四关键词被过滤；
关键词过滤不等于四个都虚构，存在词形匹配问题。旧详情18个英文标题实际上与
最终正文标题一致，不能把旧报告“标题回退”当作已核实根因。

用户随后报告 News c038/c005/c040 的 Grok 原生详情 POC：三份一次通过结构校验，
生成每篇44–46秒，准备到复核约7分钟；背景和归因更克制。当前 Mac 未找到这次
POC附件，以上 POC质量描述来自用户报告，不冒称逐字独立复核。
报告问题：正确答案经常最长；多写 PBS NewsHour host 头衔；data shows 和
why_it_matters 推断超出原文；未洗牌、未独立审核、未检查中文。

决定：DeepSeek保留正文批量调用，Grok在最终修稿之后直接生成详情，不再追加
详情模型审核。正常三栏由21次DeepSeek降为3次，新增9个原生详情任务；没有
额外单独DeepSeek选题调用，八选五和五篇正文仍是同一次调用。Grok用量可能增加，
必须实测，不能承诺低于3%。本轮不重新生成中文，不把一次中文抽查当全量检查。

## 新的完整流程与职责

1. Python只读读取当前启用来源和本栏目D-7≤日期<D的已发布事件，冻结registry。
   同一天重跑视为覆盖，排除D当天；每栏独立历史，不跨栏扩大21条窗口。
2. Python采集RSS摘要、清理URL和完全相同标题。Grok计划任务用元数据筛选、
   同栏历史事件判断、重要性、趣味性和分栏，保留每栏最多30项完整备用目录。
   公共事务科技/AI及政府动物外交留News；趣味科技/动物趣事入Fun；动物生物学、
   physics/chemistry/astronomy/biology留Science。计划并非只取三条标题。
3. Python按排名按需抓原文与来源图：目标每栏最多8篇合格原文，同时检查词数、
   图片解码/大小、WebP和缓存哈希；每栏抓取预算12次，失败也计数。不能先读全部
   99篇正文。Science优先不同科学题材，合格情况下至少两出版方；News重要性先于
   多样性；Fun兼顾游泳/网球、真正趣味，排除大学招募、无趣讣闻及消费导流。
4. DeepSeek每栏一个调用从最多8篇选择5篇，给标题/理由并生成easy、middle、中文
   正文；不生成详情。News第一稿为被选入草稿中的最高重要性稿，skipped需解释。
   不再另加一个DeepSeek预选调用。
5. Grok每栏一个选稿任务把5篇排为3篇优先、2篇备用。重要News第一优先，其他两篇
   尽量不同题材；Science优先不同学科及两出版方。不是硬用来源数量压过稿件质量。
6. Grok仅修所选单篇：修归因、引语、限定语、中立性与儿童表达，并给修后评分。
   不合理稿先定点修改，不整组重写；仍不合格换备用；仅该栏需要时局部补稿。
   Science/Fun无额外严格事实审核调用，但仍不能放行虚构事实/结果/引语；final
   facts_supported仍需为真。News战争/政治可解释，删血腥细节、重复恐惧和编辑过程话。
7. 最终三篇冻结后，Grok每篇一次原生详情任务同时生成easy/middle详情。
   只输出六个增强字段；不能输出或改正文、标题、中文。观点只取原文有出处立场，
   背景可为空；不发明头衔/年份/数字，不把观点说成数据证明。每级6道题从该级
   正文作答，四选项长度/语法平行，正确答案不能习惯性最长。生成后同模型自检。
8. Python过滤不在该正文的关键词、严格校验结构、确定性洗牌；若至少4/6答案
   唯一最长则告警，不新增模型调用、不拒整篇。洗牌只解决位置偏差，不解决长度提示。
   有限格式修复失败可省略详情保留正文并告警；不会盲目重写整组。
9. Python复用缓存图、核对正文词数/ID/结构/哈希、生成site与publication.zip并check。
   本轮停止在本地ZIP，禁止发布/上传/写库/邮件。现有来源图机械检查保留，不声称
   实际视觉批准。ZIP消费者P1–P5仍阻塞生产启用。

News此新模式至少两家合格出版方即可，不再因两家而告警；Science仍两家、Fun仍三家。
没有合格重要News时明确告警，不能编造重要性。不能为了凑三篇搬昨天成品。
2026-10-01补充：孩子关注的知名网球/游泳明星的当前比赛、复出、精彩表现、纪录，
同质量合格稿中优先于一般体育/职业回顾；不能因退役情感强就自动优先。
同一规则传到计划/八选五/五选三，不增加调用；安全/事实/历史优先，旧profile不改。
正式模板/测试站/DB归档切换计划见KIDSNEWS-SAFE-TRANSITION-2026-10-01.md。

## 恢复、模型与真实性

新profile冻结进input.json。不要把旧batch-quality-1切换模式，不改已完成答卷。
exit2是原生任务交接，读指定request，写指定answer，然后同目录重跑；exit0继续，
exit1暂停真实错误，done停止。状态/缓存/任务预算不删，不重置。默认不启用HTTP
原生兜底；超过24小时必须新history并confirm-stale。细节见ZIP runbook。
详情报告明确“Grok原生生成并自检；Python结构校验；无独立详情审核”。
passed仅代表该阶段验收，不代表独立事实安全证明。所有模型版本/调用/耗时按实际日志记录。

## 给 Bot 的完整测试消息

```text
在 /workspace/kidsnews-shadow 做一轮新的三栏影子测试，停在ZIP，禁止发布、上传、
部署、数据库写、邮件及修改代码/规则。先git status确认干净，再pull --ff-only
origin codex/stepwise-full-shadow；确认UPSTREAM和分支。阅读BOT.md、AGENTS.md、
agent/skills/kidsnews-shadow/SKILL.md及本文件。不打印.env/密钥。
装现有pipeline/requirements.txt，用.venv/bin/python。日期D取America/New_York当前日。
使用全新work/D/batch-grok-details-1（若已存在请用新编号，不删旧目录）。
用现有连接器只读取得启用source configs及每栏D-7≤日期<D且archived=false历史，
写该目录registry.json，确认history存在且非全零。不是把旧影子标题加入发布历史。
运行：
.venv/bin/python -m pipeline.agent_shadow prepare --date D --editor-mode autonomous --test-profile batch-grok-details --registry work/D/batch-grok-details-1/registry.json --run-dir work/D/batch-grok-details-1
.venv/bin/python -m pipeline.agent_shadow step --run-dir work/D/batch-grok-details-1
将D和目录编号替换成真实值。按next/rerun逐步执行；exit2读request写answer，只复制
给定request_id；完成后同目录继续。禁止盲目循环exit2和修改已完成答卷。
modifier任务用新会话仅读本任务，最终文章改好再给判断。详情任务直接原生生成并
自检，不再另开详情审核、不生成或覆盖正文/标题/中文。只有一个坏稿就修那篇。
脚本如exit1停报原因，保留现场，不擅自换阈值/重置预算/重发整批。
done后运行：
.venv/bin/python -m pipeline.publication_bundle build --run-dir work/D/batch-grok-details-1 --zip work/D/batch-grok-details-1/publication.zip
.venv/bin/python -m pipeline.publication_bundle check --zip work/D/batch-grok-details-1/publication.zip
保存所有调试文件，不清缓存。若有内置日志push，先说明目标与脱敏规则，不推main。
只在完成/阻塞时汇报：ET起止、各阶段时间、8/5/3实际数量、历史数、抓取与图片次数、
DeepSeek逐次任务名和token、原生任务数/时间、替换/拒稿原因、最终标题/来源/题材/
重要性、详情被省略和最长答案告警、ZIP文件数/字节/SHA256。Grok账单未知就说未知。
发送ZIP、report及9份原生详情JSON供人工检查，不声称已部署或收件箱已收到邮件。
```
