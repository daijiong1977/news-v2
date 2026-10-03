# 固定五选三运行说明（2026-10-02）

2026-10-03：新目录自动启用三天时效Python门禁（News/Science/Fun均适用）。
无需新增模型调用或手动删稿；旧目录续跑不重筛已接受稿。
publication date、明确开头事件日期、未知日期处理见当前Spec开头。

## 当前新轮：真正三阶段

按 `KIDSNEWS-THREE-STAGES-2026-10-02.md` 执行：
1. kidsnews_bot --stage prepare，一次完成Python＋DeepSeek准备。
2. Grok读取groups三份request，连续保存selection及九篇成品，不穿插Python。
3. kidsnews_bot --stage finalize（可显式--publish），统一校验/打包/交现有CI。
旧无--stage入口仅供旧目录恢复，不能用于已有groups/manifest的新目录。

## 以下是历史逐任务接口（旧目录恢复）

当前 Spec：KIDSNEWS-FIXED-FIVE-2026-10-02.md。旧 source-first-grok 目录继续原模式，不改 input。
新入口 `pipeline.kidsnews_bot` 自动连续做准备、跳过便宜Python边界、打包并按显式参数交付。

## 开始前

在VM /workspace/kidsnews-shadow 拉 codex/stepwise-full-shadow，安装 pipeline/requirements.txt。
DeepSeek key 已由用户放 .env；不要打印。发布凭据只在Bot仓库CI，不需要VM service-role。
按原 registry_snapshot/只读连接器取得当天sources与七天真实history；下载 website-effective-history ledger并overlay。
日期用America/New_York；所有work状态、原文图片和调试文件保留。第一次用新目录。

## 一个入口，完成后同目录恢复

D/RUN替换真实日期/运行名，registry先准备。当前用户授权网站试发，但不写DB/archive：

```sh
cd /workspace/kidsnews-shadow
git pull --ff-only origin codex/stepwise-full-shadow
.venv/bin/pip install -q -r pipeline/requirements.txt
.venv/bin/python -m pipeline.kidsnews_bot --date D --registry work/D/RUN/registry.json --run-dir work/D/RUN --publish --ack-same-day-replacement --branch codex/website-release-D-RUN
```

只看ZIP、不发布：省略最后三个发布参数（--publish、--ack-same-day-replacement、--branch）。
命令会连续完成步骤1–6（每栏排序前8、生成5篇Easy/Middle/中文，共15篇）。
之后每次exit2，只读返回的read文件，按原生协议写write_to；request_id一致，content为JSON字符串。
**写完重跑同一个kidsnews_bot命令**，不要按旧rerun直接跳到pack。Grok按组任务返回五个ID顺序，
并逐篇修稿＋两级详情＋自检；三篇来自固定五篇，不能后补、搜索、改代码或篡改已接受答卷。
Python按原有有限修正/详情降级管理失败。正文改动同步详情，名词解释不能编造事件事实。

- exit2：需要当前原生答卷或答卷修正；不是挂住，不循环空跑。
- exit1：真实错误/硬校验或固定组不足，保留断点和报告；不要换目录清零或重写整个五稿。
- exit0 checked_local_zip：本地reader已检查，未发布。
- exit0 ci_verification_pending：artifact已推送，等待Bot Publish website-only reader Actions；不是网站成功。
- 子命令exit3：已完成，入口会继续到打包/既有交付回执。
- 超过24小时：刷新真实history，再显式加 --confirm-stale，沿用原目录和目标日。

正常无修复基线6次DeepSeek（排序3＋正文3）、12个Grok任务（组选择3＋逐篇成品9）。
数字仅是调用基线，不承诺实际token/账单。

## 发布与失败恢复

输出publication.zip为内部包，reader-artifact/reader.zip为公开正式模板包。
四份批准artifact自动到新的codex/website-release-*分支，触发Bot已有publish-reader.yml。
Actions备份旧对→latest两对象→dispatch原网站Action→公网hash→私有有效历史ledger。
不写文章/详情/来源DB，不写日期archive，不调用新consumer，不发邮件。
引语逐字不匹配和facts false只告警；三栏各3篇、结构/数字/适龄和hash仍要通过。
不能把push/Storage PUT/Action绿灯单独称网站已更新。

出现website-handoff attempting：先查精确远端分支SHA和CI，不盲重发。
出现latest读回失败：保留原CI backup run ID，用website_delivery显式resume；不whole-job rerun。
回滚依KIDSNEWS-WEBSITE-RELEASE-2026-10-01.md，使用原备份对；其他写入者冲突必须停报。

日志仍自动到私有logs分支（VM hostname守卫），本机测试不推日志。
交付一行：counts、ZIP路径/hash、CI链接与公开验证状态、重要警告/耗时/token。
先不建立新的每日例行调度，不清缓存。新模式真实质量/费用及真实回滚待VM验收。
