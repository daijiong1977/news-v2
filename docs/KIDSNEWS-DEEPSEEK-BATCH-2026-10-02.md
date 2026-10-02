# DeepSeek 五篇批次：上下文、输出与排序

仅影响影子批次与 source-first 配置；生产 full_round/news_rss_core 不改。

## 已核验

2026-10-02 官方 pricing/API 文档与本机账号 GET /models 一致：
deepseek-flash、deepseek-v4-pro context_window=1048576，max_output_tokens=393216。
今日旧请求最高输入24537 token，不是上下文不足；Fun finish_reason=length，
输出8191，碰到了调用方8192上限。News旧prompt同时包含每个输入返回和只选五篇，
出现五完整稿及三article:null。两次格式恢复未改原五篇正文。

## 新请求

- 独立 batch_prompt，不再拼生产单篇提示词和批次override。
- 五篇完整对象，drafts按最好到最差顺序（前三优先、后二备用），各有简短理由；
  未选ID仅放skipped，不允许null、重复、额外稿或复述输入。
- HTTP批次：max_tokens=16384、response_format=json_object、thinking=disabled、
  temperature=0.2。原生任务不增加HTTP参数，不把8192额度带给原生兜底。
- source-first新轮配置使用deepseek-flash；不更改旧目录冻结的providers.json。
- 英文按每候选body_word_bands的中点写，不能贴下限；中文200–300汉字。
- News重要稿优先；Science学科/出版方多样；Fun趣味/体育明星偏好；
  原文支持、儿童安全、中立和同栏历史规则保留。Grok可参考并调整最终顺序。
- 16K是容量上限，按实际token计费；1M不是要发送1M材料。原文仍仅给选中八篇。
- Python仍检查答卷，不因JSON mode宣称格式/篇数/字数必然正确。
- 新目录才能对照新prompt；不要改已完成答卷或重写已冻结整组。

## 验证

test_batch_prompt_contract 三项先失败、修复后通过；相关Python3.10回归实测。
本机真实测试仅复用今日缓存Fun八篇，不重新抓取、不Grok、不发布/写库/邮件。
第一版约20.28秒，27495 token，五对象、stop，但两篇英文贴下限不合格；
因此增加按区间中点目标和双级逐篇计数要求。第二版仍多返回行及超字数；
发现body和paragraphs重复传全文，故精简为每篇完整body一次。第三版输入10936/
输出6149、28.95秒，英文范围通过，但两zh用了body而不是summary；加明确字段约束。
最终版27.16秒，输入10987/输出5935/总16922，finish_reason=stop，恰好五个唯一
完整对象，中文字段正确，无额外行/null/截断。Easy分别243/276/273/256/225，
Middle344/401/359/341/345；两Easy分别超270上限6及3词。不能宣称逐篇字数全通过，
交既有Grok逐篇精修减少几词，不重写五篇、不放宽校验。本次不进一步循环调用。
合计四次受限缓存Fun对照，不调用Grok、不写生产。两仓库3.10回归259项通过。

## 已同意但本补丁不涉及的采集调整

Science/Fun每栏目标10篇合格，每源目标3篇（2篇保留）、3→3最多6；
News不变。此独立采集规则尚未修改collect，不能把本次prompt补丁称作已落地。

参考：https://api-docs.deepseek.com/quick_start/pricing/ 、
https://api-docs.deepseek.com/api/create-chat-completion/ 。
