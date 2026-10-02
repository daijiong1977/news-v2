# Kids News：Python → Grok 文件工作 → Python

2026-10-02 当前新运行合同。优先于旧“每答一题就重跑入口”说明。
profile仍为source-first-deepseek；必须新目录，旧实验目录沿原模式恢复。
实现：pipeline/kidsnews_bot.py 的 --stage prepare / --stage finalize，以及
pipeline/kidsnews_groups.py。两条命令不是伪装旧逐任务循环。

## 一、Python 一次准备完

先准备当日只读 registry（sources、过去七天 history，叠加已核验网站 ledger）。
来源采集和筛选规则仍以 KIDSNEWS-FIXED-FIVE-2026-10-02.md 第一部分为准。
在VM /workspace/kidsnews-shadow，D/RUN替换真实美东日期和新运行名：

```sh
.venv/bin/python -m pipeline.kidsnews_bot --stage prepare --date D --registry work/D/RUN/registry.json --run-dir work/D/RUN
```

Python抓全文/图、执行机械过滤；DeepSeek Pro每栏一次编号/摘要前8排序，Flash一次选五写稿，两者均关闭thinking。
新目录使用indices-v1编号映射和统一ranked JSON；详情见KIDSNEWS-PRO-RANK-2026-10-02.md。
Python过滤明确不适龄/错栏摘要、重复事件和模型标记的历史重复；少于5篇先报告shortlist_shortfall，不付费写不完整组。
正常基线6次DeepSeek；只抓缓存缺失内容，不让Grok另做plan或浏览。
输出drafts-for-grok.json（每栏5篇，共15篇Easy/Middle英文稿和中文标题/摘要），
groups/manifest.json，以及groups/News-request.json、Science-request.json、Fun-request.json。
每个request自包含5稿、原文、同栏历史、字数范围、Python审查、编辑prompt和答卷schema。
输入、原文批次、catalog和request被哈希锁定，不允许Bot修改。prepare禁止--publish。
完成exit0、stage=grok即进入第二步，不要继续agent_shadow step。

## 二、Grok读结果，连续完成三栏九篇

一次只读一个栏目request，依次完成News、Science、Fun，避免反复读取整个上下文。
从固定5篇完成3篇，完整五ID顺序放selection中，最终三篇在前，两篇备用。
每篇修正文、生成两级详情、自检合并一次，立即保存成品，再下一篇。
此阶段不运行中间选稿/审核Python、不另开模型审核、不调用外部API、不发布。

给Grok的编辑prompt（完整字段规则在各栏目request.prompt中）：

> 阅读该栏目request。DeepSeek排序和python_audit供参考；你从固定5篇完成最好的3篇。
> News重要适龄新闻第一；Science尽量学科/出版方不同；Fun优先真正趣味与当前游泳/网球明星。
> 这些是软偏好，必要时放宽；不能后补第六篇。逐篇完成正文精修＋Easy/Middle详情＋自检。
> 保留Easy、Middle和中文标题/摘要。删不适龄细节、修归因和限定语；必要时加入准确通用解释，
> 但不能编新闻事实、数字、年份、引语或无出处的另一方观点。背景/观点可以为空。
> 各级题目只依据对应最终正文；选项长度平衡。按request的schema保存，每篇写完立即存盘。
> 不搜索、不改代码/规则/输入、不删缓存。三栏九篇文件写完才进入最后Python。

选择文件：groups/<Category>-selection.json：
```json
{"request_id":"复制对应request_id","order":["最终1","最终2","最终3","备用1","备用2"],"reason":"选题及放宽软偏好的理由"}
```
成品文件：groups/answers/<Category>-<ID>.json：
```json
{"request_id":"复制对应request_id","id":"候选ID","value":{"corrected_article":{},"details":{},"scores":{"0":{}},"facts_supported":true,"event_clear":true,"notes":"具体自检疑问；无疑问可空字符串"}}
```
示例空对象仅展示外层，必须按request.prompt填全。value是对象，不是JSON字符串；
source_id固定0，详情槽0_easy/0_middle，自检scores.0含八维0–5分。
五稿不等于ready；Grok自检不是独立审核，facts false只告警，不是事实准确证明。

## 三、最后Python统一校验、打包、交给现有发布CI

```sh
.venv/bin/python -m pipeline.kidsnews_bot --stage finalize --run-dir work/D/RUN --publish --ack-same-day-replacement --branch codex/website-release-D-RUN
```

只看本地ZIP：省略三个发布参数。此命令不调用任何模型，也不新增全文抓取。
逐篇复用原有限修正校验，持久保留ready；字段/字数/安全/历史/图片/hash仍硬门禁。
引语逐字不匹配和facts_supported=false只告警。详情可额外定点修一次/删坏增强字段，
仍坏则省略对应详情模块，保留合格正文。不能伪造九篇通过。

- exit2：指定某一答卷/selection要修；看errors和groups/repair.json（若有），只修该文件后重跑finalize。
  正文修正一次；详情失败按状态额外一次。别整组重写、重复DeepSeek或改已经接受的文件。
  某篇仍坏可换同五篇中备用；已通过稿保留，固定五篇耗尽仍不足3则停报，不能补第六篇。
- exit1：工具/锁/hash错误，保留目录停报，不自己改代码、清预算或换目录重来。
- exit0 checked_local_zip：正式模板ZIP完成但没上线。
- exit0 ci_verification_pending：批准artifact已push，等待现有CI；不是上线成功。

采用锁定完整commit/hash的正式reader-shell，包括.jsx。私有publication.zip与公开reader.zip分开。
只把四份批准artifact交Bot现有publish-reader.yml；CI备份latest对、上传、等待读回、dispatch
原kidsnews-v2 Action并做公网hash核验。Action保持原方式。数据库/date archive/邮件不动。
未知push/上传结果不盲重发；按原backup_run_id恢复，不whole-job rerun重备份半写状态。
本轮不创建例行任务。缓存/调试文件全保留；阶段时间和答卷自动进入私有logs分支。

超过24小时：停止自动接受旧历史；同目录finalize加--confirm-stale --registry新只读registry。
Python输出一个文件式history-refresh请求，Grok核对固定15个ID同栏历史后写答卷，重跑finalize。
不重新写稿、不调用模型API、不改原目标日/冻结input。已接受稿后来确认为重复则停报维护者，
不能为了3篇目标绕过新历史。已完成包不追溯重做历史。

## 验收边界

离线测试覆盖真正两次Python入口、单行JSON、15→9、最后阶段零模型调用、定点修正、
详情合法降级、已接受稿不可改、缓存不可改、跨天文件式历史复核与旧模式兼容。
真实质量/费用/公网发布和回滚必须VM验收；离线mock不证明真实部署成功。
