# 2026-09-27 Kids News 修复总结与复用指南

本页记录当天的 PR #65–#69 和来源表操作。具体阈值和代码入口以 [栏目规则](editorial-category-routing.md) 和 [流水线漏斗审计](pipeline-funnel-audit-2026-09-26.md) 为准；本页记录问题、验证边界与可以复用的方法。

| 问题 | 修复 / 所在位置 | 可复用的做法 |
| --- | --- | --- |
| 同一事件的不同阶段、改标题的相同 URL、跨栏目重复 | [#65](https://github.com/daijiong1977/news-v2/pull/65)：先用规范化来源 URL 和过去 7 天三栏记录过滤，再做 Jev 同事件判断；题材标签只用于软性多样化 | 每次接入新栏目或来源时，共用跨栏目事件窗口与 URL 规范化，不把“不同题材”误作“不同事件” |
| News / Science / Fun 错栏，Fun 体育被统称为一个题材 | [#65](https://github.com/daijiong1977/news-v2/pull/65)：Jev 高置信度路由；Fun 分 swimming、tennis、other_sports；重大比赛、冠军和纪录获得软性优先级 | 在栏目选择之前统一分类政策；运动员名字或体育标签本身不等于值得报道的新进展 |
| 文章过长或过短；自动修复可能留下仍不合格的正文 | [#66](https://github.com/daijiong1977/news-v2/pull/66)：DeepSeek 最多两次有来源上下文的修订，按实际词数验收；归档修复后重新做独立全文儿童安全审核 | 把模型输出当候选，发布前用确定性指标和独立审核验收；同样适用于其他自动改稿流程 |
| 三篇来自三个 feed，却都属同一出版方 | [#66](https://github.com/daijiong1977/news-v2/pull/66)、[#69](https://github.com/daijiong1977/news-v2/pull/69)：安全合格后尝试不同来源备稿；ScienceDaily 多 feed 合并计算为一家出版方，Science 目标至少两家 | 来源多样性按出版方审计，备稿也必须经过原有安全和质量门槛；目标达不到时报告，不放宽安全门槛 |
| Fun 候选偏少，大学招募稿占了游泳位置 | [#67](https://github.com/daijiong1977/news-v2/pull/67) 把首轮来源上限从 8 提到 10；[#69](https://github.com/daijiong1977/news-v2/pull/69) 将 Fun 送主编上限设为 7，并在采集、备稿、续跑和打包等路径排除大学招募 | 扩大低成本候选池之后仍要看每层漏斗的损失；编辑禁入规则要覆盖所有回流路径 |
| 只按一般吸引力选稿，缺少各栏目价值判断 | [#69](https://github.com/daijiong1977/news-v2/pull/69)：利用现有 Jev 请求评估 News 对美国儿童的重要性、Science 的学习价值、Fun 的趣味性；重要 News 获软性优先级 | 在现有评分请求中加可审计的栏目特定维度，再用人工标注样本校准阈值；不以高分绕过独立安全审核 |
| CBC RSS 请求卡住，News 来源不足 | [#68](https://github.com/daijiong1977/news-v2/pull/68)：有时限的 HTTP 获取和明确的 RSS User-Agent，再交给 feedparser；CBC World 已在来源表启用 | 新来源先测 RSS 响应、近期条目、正文可提取性；获取器有固定超时，来源配置和代码分开回滚 |

## 当天来源表状态

- News 当前启用 BBC News、CBC World、NPR World、PBS NewsHour；Al Jazeera 停用。
- Fun 新启用 TIME for Kids（ID 364）和 BBC Swimming（ID 365）。BBC 游泳 RSS 返回 200 且最近一周有新条目；TIME for Kids 有近期内容，但 RSS 存在一个解析警告及不同年级的同题版本，后续应观察去重结果。
- 按用户要求从来源表删除停用的 MIT Tech Review（原 ID 110）和 IEEE Spectrum（原 ID 338）；前者当前内容偏成人政策议题，后者的 RSS 返回 403。
- 这些是 `redesign_source_configs` 的直接配置操作，不属于 Git 提交。当前源表启用数：News 4、Science 13、Fun 16；未来应以运行当天的表状态为准。

## 已验证与待观察

- #69 在旧于最后两次动物 / Tech / AI 栏目规则修订的提交 `f3b65e0` 上，完整重跑 2026-09-26：9 篇发布，Science 来自两家出版方，独立儿童安全审核均为 scored/PASS，九篇 middle 正文均在 300–410 词内；[运行记录](pipeline-rerun-2026-09-26-pr69.md)。新栏目修订已过离线测试，但还需要下一次自然定时运行观察。
- 当次 Fun 只有 4 篇达到送主编条件，7 是上限而不是保证；新增来源的实际贡献、Jev token 和时间成本尚未由定时运行证实。
- News 的重要性评分当次没有达到高优先级阈值，即使东北暴雨紧急状态只有 2.82；需要人工标注样本校准。音乐稿中的歌名语言边界也需要编辑规则讨论。这些是记录中的未解决问题，不能宣称编辑质量已全面通过。
- 本页不要求手动重跑。合并后监控首次 main 定时运行和网站同步，记录每栏候选数、来源 / 出版方、独立安全结果、7 天去重、耗时和异常。
