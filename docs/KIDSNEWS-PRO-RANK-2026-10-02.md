# Pro摘要排序、选题提示词与JSON格式修复

2026-10-02。适用新建source-first-deepseek运行目录。三大步入口不变。

## 模型分工

| 阶段 | 模型 | 输入 | 输出 |
| --- | --- | --- | --- |
| Python内摘要排序 | deepseek-v4-pro，thinking关闭，JSON模式，4096输出上限 | 本次候选编号＋标题/RSS摘要，同栏七天历史标题/摘要 | 按优先级最多8篇 |
| Python内选五写稿 | deepseek-flash，thinking关闭，JSON模式，16384输出上限 | 已缓存原文，每篇仅传一次 | 每栏5篇Easy/Middle英文＋中文标题/摘要 |
| Grok阶段 | Bot原生Grok | 固定五稿和原文 | 从五篇完成三篇精修、详情和自检 |
| Python finalize | 无模型调用 | 三栏九篇成品 | 校验、ZIP、原有网站交付 |

配置：config/shadow-source-first-deepseek.json。旧目录继续用providers.json中冻结的模型；新配置不覆盖恢复中的旧任务。input.json和prepare-context.json冻结shortlist_contract=indices-v1；没有此标记的旧目录沿旧答卷协议恢复。用新目录才启用整套新排序规则。

## 排序协议与提示词

pipeline/agent_shadow_rank_contract.py为新协议单一入口，不再拼接“30篇catalog”和“前8篇override”两套输出要求。

候选对外仅{id:1, abstract:"标题\n摘要"}。编号是本次请求内1开始的整数，Python保存index_to_id精确映射；全文和真实长ID不发给排序模型。返回仅{"ranked":[...]}，每项包含id、topic、importance、initial_risk、history_status、history_confidence、event_key。字段类型、枚举、范围和未知/重复编号均检查；不模糊修正错ID。

选文顺序：适龄与儿童意义 → 正确栏目 → 同事件/同栏七天历史去重 → 重要性和趣味排序。News选最重要的合适稿，不能以死亡数字替代重要性；Science兼顾物理、化学材料、天文、生物、地学，来源多样性在收到真实出版方后的写稿阶段处理；Fun关注真正趣味、儿童动画、游泳/网球明星与当前成绩。

明确不适宜的性侵/处决不会因官员回应而成为儿童政治新闻。研究/新物种/演化、农业增产属于Science；动物趣事归Fun，动物悼念、成人服饰、点歌投票和演唱会歌单不凑名额。Python对这些有明确摘要信号的案例做窄过滤，原因落在shortlist-exclusions-栏目-8.json；保留原始候选，不跨栏目全局删除研究稿。这些规则不等同全文安全判定。

模型若仍返回history duplicate/uncertain、confidence<0.7、risk>=4，Python移除并记录原因；同event_key规范化后只留排名最前的一篇。event_key依赖模型语义判断，不是完美事件识别。最终Grok及原有历史校验仍保留。

未凑够5篇时，写shortlist-shortfalls.json并返回shortlist_shortfall，发生在任何五稿写作调用之前。不能用不合适稿凑满，不能让Bot自行删状态/降安全要求。该缺口发生在固定五篇形成之前，不改变第二阶段固定五选三规则；本补丁没有实现追加来源采集。

## 格式恢复

pipeline/agent_shadow_batch_json.py统一机械JSON解码：可去除独立JSON代码围栏、字符串之外的尾逗号、已验证的多余右括号。五稿答卷中误放在article外的zh可移回同篇article内。原答卷和文章文字保留，修复操作及原文哈希分别记rank-format-recovery.json / batch-format-recovery.json。

重复键、冲突zh、截断正文、未知ID、不完整/含歧义结构不会被补造。JSON格式和选题合格是两个检查。失败仍走原有有限定点修复；不重新生成整组五稿。

## 证据与限制

此前同摘要A/B共12次调用，全部关闭thinking：Pro六份通过原校验，Flash三份通过；强化提示词组三栏Pro用10,242输入/1,100输出token，闲时估算$0.00828，比Flash多约$0.00641/天。样本仅一天，不能推断长期准确率。

本补丁的数字编号协议再用真实摘要走实际TaskRouter/ask调用Pro三次，均一次JSON/ID/历史状态校验通过，约2.9/4.2/3.8秒，无reasoning。复核发现模型仍会把研究/悼念/投票归Fun，故补入上述Python窄过滤，并以真实坏例和正常Science/游泳/网球/机器人/动物救助例回归。修正前后三份原始HTTP答卷未被改写。测试输出在本机/tmp/kidsnews-rank-ab-3jy2DB/implemented-pro。

当前旧摘要池经规则处理，News不足5篇；Fun旧答卷中的6篇有4篇会被明确过滤，仅Messi动画和机器人合适。这是候选不足，不是JSON故障。Science/Fun每源3→3、全栏10篇及更多体育来源机会仍为待办，未在本补丁实现。未进行新轮完整写稿/上线，不把格式通过当作内容发布合格。

Python3.10回归覆盖数字编号精确映射、坏ID拒绝、同事件/历史/风险过滤、新旧目录恢复、三栏排序到15稿及断点复用、JSON字面字符串保护和坏格式拒绝。完整测试结果写入本次PR。

价格来源：https://api-docs.deepseek.com/quick_start/pricing/ 。费用按返回用量和官方价格估算，账单以服务端为准。
# 数量规则后续更新

新目录的 selection_policy=twelve-five-three-v1 以每栏首批12篇为目标，Pro选5–8个不同合格事件，不足时由Python补采该栏下一配置源并重排。允许同来源、同学科；同事件与七天历史去重不放宽。固定五篇交给Grok完成三篇。以下旧样本的4/2缺口是当时测试证据；入口补采代码现已补齐，新的真实VM全轮仍需验收。
