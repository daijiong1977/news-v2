# Kids News 网站先行：运行与审核说明

日期 2026-10-01。配套合同：KIDSNEWS-WEBSITE-ONLY-SPEC-2026-10-01.md。
**本文件为审查前历史运行说明；修复后的完整执行入口已移到
KIDSNEWS-WEBSITE-RELEASE-2026-10-01.md，请只用新文件中的命令。**
本文不是让 Bot 现在上传的 prompt，不使用虚构的 publish-latest/rollback CLI。

## 1. Cloud 先审，再运行

审查顺序：新 Spec → 本 Runbook → 两仓库 AGENTS/BOT → 矩阵指定代码及测试。
先评需求逻辑，再逐条检查代码匹配。先报告缺口，不自行部署/改 DB/触发 workflow。
旧 SAFE-TRANSITION、RESUME-REVIEW、8-5-3 文档按日期保留；冲突以新网站阶段
边界为准，已完成旧目录的冻结 task 合同不能倒改。

可转发给 Cloud：

```text
请只读审核 Kids News 网站先行迁移方案，不改代码、不调用模型、数据库写、上传、
部署、邮件或工作流。先完整读：
/Users/jiong/myprojects/grokbot/grokbot-kidsnews/docs/KIDSNEWS-WEBSITE-ONLY-SPEC-2026-10-01.md
/Users/jiong/myprojects/grokbot/grokbot-kidsnews/docs/KIDSNEWS-WEBSITE-ONLY-RUNBOOK-2026-10-01.md
再读两个仓库 AGENTS.md 与 Bot 的 BOT.md。
共享源码 /Users/jiong/myprojects/news-v2-agent-provider，codex/agent-provider-boundary，PR86；
Bot /Users/jiong/myprojects/grokbot/grokbot-kidsnews，codex/stepwise-full-shadow，PR1。
先判断 Spec 是否合理完整，再逐条对照实现。区分已实现、待实现、待真实验证，
不要把矩阵已声明的计划当成声称完工；但需要指出哪些缺口阻塞第一阶段上线。
重点：正式模板.jsx及依赖、公开reader包不泄露内部材料、旧manifest字段、latest-only
写入边界、非原子双对象/定时读竞态、备份和同日回滚、旧writer/自动修复覆盖、
网站/DB不同稿时搜索与阅读ID风险、未入库Bot稿次日有效历史overlay、持久状态、
Storage/dispatch身份与权限、公开hash验证。
不要求第一阶段做数据库/archive的P1–P5或全库回滚；这些必须保持停用。
给出P0/P1/P2问题、代码文件/行、影响、最小修正建议及验收测试；另给Spec↔Code矩阵。
能运行不联网的离线测试；不要将离线通过当成正式部署/回滚已演练。
将结论写为 docs/KIDSNEWS-WEBSITE-ONLY-REVIEW-2026-10-01.md，不自动commit/push/merge。
```

## 2. Bot 安装与生成（现有命令）

用户在 VM 终端操作；Mac 不向远程串流直接打字。先确认干净及正确分支，
不打印 .env、不覆盖已运行任务。拉取失败停止本次正式试用，不用未知旧版发布。

```bash
cd /workspace/kidsnews-shadow && git status --short && git branch --show-current && git rev-parse HEAD
```

干净且分支正确后：

```bash
cd /workspace/kidsnews-shadow && git pull --ff-only origin codex/stepwise-full-shadow && .venv/bin/pip install -q -r pipeline/requirements.txt
```

读 BOT.md、AGENTS.md、agent/skills/kidsnews-shadow/SKILL.md 和本次 Spec。
D 为 America/New_York 当日，RUN 取全新编号；以下 D/RUN 是占位符，不能原样运行。
registry 用现有只读连接器取得启用来源及同栏七日历史；有效网站 overlay 实现后
须一并合并。本阶段发布需该功能验收；仅当前影子质量测试可保留 DB 历史原样并注明。

```bash
.venv/bin/python -m pipeline.agent_shadow prepare --date D --editor-mode autonomous --test-profile batch-grok-details --registry work/D/RUN/registry.json --run-dir work/D/RUN
.venv/bin/python -m pipeline.agent_shadow step --run-dir work/D/RUN
.venv/bin/python -m pipeline.agent_shadow status --run-dir work/D/RUN
```

- 按 stdout next/rerun，一次一个单元；exit 2 是任务交接或有限修复，读指定 request，
  写对应 answer/request_id 后同目录继续，不能循环调用等待文件自己出现。
- modifier 用新任务会话，修所选稿一次并自检；详情同一次生成自检，无单独审核。
- exit 1 停止报告真实故障；exit 0 按 next；already done 时不重复生成。
- 不删状态/预算/答卷。超过24小时按现 CLI 的 confirm-stale + 新registry显式复核，
  不偷偷改日期；具体以 SKILL/current next 为准。
- DeepSeek传输兜底仅显式prepare选项开启且冻结；不为省事临时更换profile。

## 3. 现有 ZIP 命令与正式包门槛

生成完成后可执行（仍只是内部影子包）：

```bash
.venv/bin/python -m pipeline.publication_bundle build --run-dir work/D/RUN --zip work/D/RUN/publication.zip
.venv/bin/python -m pipeline.publication_bundle check --zip work/D/RUN/publication.zip
```

正式模板入口已有 --shell-dir，但遗漏.jsx尚未修复；现在不提供可直接发布的
build命令。实现后正式 reader 副本使用明确 commit，不从含未提交变更的 checkout
盲拷；内部包保留不覆盖，另生成 reader.zip。预览通过再做逐文件引用与hash校验。
原 publication_bundle upload 投递 pending ZIP，agent_shadow publish 部署独立影子站，
**两者都不是第一阶段 latest-only 发布，不得调用替代。**

## 4. 发布前操作单（适配器实现后）

1. 确认Cloud问题已关闭、测试通过；记录真实source/template SHA及公开ZIP hash。
2. 用户批准具体日期/包/目标及恢复路径。批准不意味着代码PR自动merge。
3. 确认Storage latest写权限与GitHub dispatch执行身份；没有权限停在包，不索要聊天密钥。
4. 检查旧Daily/republish/quality等writer、在途同步和worker；选无冲突操作窗口。
5. 下载latest.zip + latest-manifest，核对匹配；持久独立备份并确认可从另一位置恢复。
6. 写attempt状态，再仅替换latest两对象；读回hash。发生超时先检查，不重新生成稿件。
7. 发news-v2-uploaded事件，记录时间及对应run；若通知失败，允许明确的手动同步，
   不能把定时兜底未完成说成已上线。
8. 验证对应新提交/部署及公开九篇列表、18详情、图片hash；抽查首页、阅读、题目、
   中文、手机布局、搜索/归档和同日阅读进度兼容。失败进入恢复或待人工处理状态。
9. public_verified后更新本地有效发布账本；报告DB/archive未同步。保留全部debug文件。

上述适配器尚无CLI，Cloud审核/实施完成后须用**真实实现命令**替换此操作单，
再给Bot最终运行prompt。不要让Bot现场自行写curl/SQL或重新设计恢复办法。

## 5. 网站恢复操作单

选择对应旧备份→校验ZIP和manifest→确认无竞争writer→恢复latest两对象→读回hash
→发送同一同步事件→验证公开旧文件→恢复本地有效账本。中途断掉继续此操作，
不重跑正文，不删除DB或archive。新旧包/状态保留供复盘。

已有日期恢复路径：news-v2 GitHub Actions → republish-bundle → restore_from_date=D，
trigger_kidsnews_sync=true；前提是该日期包仍等于批准的备份且manifest存在。
这会修改生产latest并触发部署，当前只列说明，未执行；如果日期包已改变用独立
备份恢复，不冒用日期入口。空restore_from_date是模板republish，**不是回滚**。
原workflow只等90秒检查同步commit，不代表Vercel已完成；继续公开核验。

## 6. 本地测试、交付与观察

- 实施新增测试用 Python3.10 + fake Storage/dispatch，不调用真实模型/生产写入。
- 测试要求见Spec第11节；原237项仅历史代码基线，不作为新发布适配器验收。
- 首次真实发布及恢复演练需分别批准；网站Action代码不改。
- 记录ET起止/各阶段耗时、来源/历史/8→5→3数、拒稿与替换、DeepSeek每次tokens/
  时间、原生任务数（账单未知就写未知）、ZIP/hash、备份标识、run/commit、公开验证。
- 这几天保留06:10旧生产与其日期archive，Bot中午在可控窗口生成/人工批准覆盖。
  不声称中午生成可省掉当天已经执行的早上成本。自动无人值守发布另行批准。
- 质量稳定后只开启第二阶段spec/schema/消费者/恢复审查，不自动运行入库function。
