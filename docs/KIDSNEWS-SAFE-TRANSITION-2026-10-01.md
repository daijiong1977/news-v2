# Kids News：明星优先与正式模板平稳过渡计划

2026-10-01，项目 kids-news-website。本文是实施计划，不是部署/迁移验收。
本轮只落实影子选稿规则、测试与文档；不创建域名/数据库表，不启用worker，不发布。

## 本轮已落实的规则

用户确认孩子喜欢知名网球/游泳明星。新batch-grok-details在三个交接点共用同一
规则：Grok元数据计划、DeepSeek八选五正文、Grok五选三。合格且质量相当时，
优先广为人知的冠军/明星的当前比赛、复出、精彩表现和纪录；不要因为退役稿
“情感强/里程碑”就自动压过孩子更感兴趣的正在进行的比赛。Djokovic是已讨论例子，
不是唯一允许的人选，也不虚构未提供的孩子喜好名单。没有合格稿不强凑体育。
安全、事实支持和同栏历史去重优先于明星偏好，News重要性/Science多样性不受影响。

本次真实日志：c077锦织圭退役与c079德约科维奇复出都为importance3、history clear，
也都在五篇草稿里。DeepSeek先给退役稿强情感/里程碑理由，Grok最终选稿c077第三，
c079第五备用。不是来源漏抓或查重误杀。提示传播的离线回归不证明真实模型一定
选c079，下一真实轮需人工验收；不追加模型调用。
旧batch-deepseek合同保持不变，旧目录不能切profile/改答卷。新轮用新目录。

## 站点、仓库与域名

| 角色 | 仓库/本机路径 | 当前边界 |
|---|---|---|
| 共享流水线 | daijiong1977/news-v2，/Users/jiong/myprojects/news-v2-agent-provider；codex/agent-provider-boundary，PR86 | 改共享影子逻辑；生产main不动 |
| Bot快照 | daijiong1977/grokbot-kidsnews，/Users/jiong/myprojects/grokbot/grokbot-kidsnews；codex/stepwise-full-shadow，PR1 | VM /workspace/kidsnews-shadow；UPSTREAM锁源码 |
| 正式reader | daijiong1977/kidsnews-v2，/Users/jiong/myprojects/kidsnews-v2/site | 复用已有模板/Action；上线前核对当前main与已部署SHA |
| 测试产物 | grokbot-kidsnews的codex/shadow-artifacts-20261001，45b405c | 独立ZIP/详情POC；不是可运行代码分支 |

正式地址记录为kidsnews.21mins.com及news.6ray.com；后者也是正式别名，不能当隔离测试站。
用户提到news.21min.com：拼写/所有权/DNS均未核验，不能直接当既有地址。
推荐先复用独立kidsnews-bot-shadow.vercel.app项目做正式模板测试，或它的独立预览URL；
后续再绑定用户确认的测试域名。生产切换是换内容生产者，不必重建网站/更换正式域名。

## 分阶段工作、验收和回退

| 阶段 | 实施内容 | 完成标准 | 粗略工程量 |
|---|---|---|---|
| A 本地正式模板 | 固定已核验kidsnews-v2 reader SHA；补打包.jsx及模板依赖清单/测试，用九篇新payload覆盖临时副本 | 首页、三栏、阅读层、题目、图、手机布局、静态资源无缺失；内容/图哈希不变，原ZIP保留 | 3–6小时 |
| B 独立线上对比 | 独立Vercel目标用正式模板+Bot内容，不改生产Action/域名；游客功能先验，登录/家长/邮件仅用隔离设置测试 | 两站同日对比3–5轮；来源轮换/查重/成本/异常恢复合格；无生产DB/最新归档/登录邮件副作用 | 4–8小时搭建+3–5天观察 |
| C DB与归档收口 | 验证live schema/约束；隔离副本测试ZIP定时消费者，备份/恢复演练，修P1–P5，发布指针与幂等 | 正文/详情/搜索/来源轮换/归档同一package；中断、重传、少稿不会删正确内容，旧新writer无竞态 | 1–2工作日，schema差异另计 |
| D 单写者切换 | PR审核后择日停旧发布writer，保留可回退；新Bot用正式shell，沿用现有站点/Action，首次人工批准 | 公开文件哈希及archive/DB一致；登录/历史阅读兼容；故障恢复旧writer+上一已核验包 | 半天准备/验收 |

合计粗估约3–4个工作日工程+观察窗口；不是交付承诺，域名权限、live schema差异和
P1–P5可能延长。仅演示正式模板无需等DB改造：先完成A，在本地确认再授权B。
这些估计来自现有代码边界，并未修改production或调用真实模型证明全部流程。

## 模板必须原样兼容

现在publication_bundle默认shell=shadow，不能原样拿去覆盖正式站。--shell-dir有入口，
但当前扩展白名单遗漏.jsx，正式index.html依赖data/components/home/article/user-panel.jsx。
必须先修并做reader依赖清单检查；不只改一项白名单就宣称所有功能通过。
复用原UI，不重设计：payloads、article_payloads、article_images格式/路径兼容；
保持文章ID/阅读层/存储字段一致，不能破坏阅读进度、积分、家长页、登录和旧归档。
先断网/无密钥的本地游客验证静态显示；auth/邮件/读取报告用隔离环境验收，不能
为了试模板给生产发信、写家长数据。模板版本与内容版本都入manifest/发布记录。

## 数据库：先复用、后少量扩展

不要凭聊天猜articles/article_detail表名。本地实现引用redesign_stories、
redesign_search_index、redesign_source_configs、redesign_runs；详情是包内JSON，
是否还需详情DB表必须核对live schema/reader查询，不默认新建第二份详情表。
新链路主要需要最终正文元数据/搜索、七天事件历史、实际使用来源轮换及归档。
中间五篇草稿/修稿/任务答卷暂留文件，不为了每个步骤建表，也不把影子稿混入发布历史。

仓库已有迁移20261001_bot_publication_handoff.sql声明两辅助表：
kidsnews_publication_receipts（包级幂等收据），kidsnews_publication_worker（消费者租约）。
有代码不代表线上已建/已部署，本轮没有检查live DB。先验证这两表能否满足需求；
如需环境/当前版本/回滚状态，再设计environment+package_id的发布记录/指针，不盲目
加很多表。影子归档用独立bucket或独立测试项目；生产latest.zip/archive-index/来源
last_used_at不能在影子阶段更新。只读来源/历史可继续来自生产。
任何新表需最小授权/RLS，浏览器不得拿service_role；迁移/备份/恢复须单独批准。

## P1–P5：上线前不能绕过

- P1：不满九篇的包不能删掉未包含栏目的现有正确文章；明确生产发布完整性策略。
- P2：ZIP/ready重传冲突先比较同一对象哈希，相同幂等，不同拒绝；中断可续。
- P3：站点/latest.zip只有一个生产writer；worker租约不能替代旧流水线停写控制。
- P4：真实表/唯一约束/字段与RPC在隔离的live-schema副本验收，不用假表绿灯替代。
- P5：当前worker先公开核验再入库；故先Git/Vercel部署同包，再verify，再ready，
  定时消费者才归档/DB。跨系统不是原子事务，失败需保留待同步状态/可回退包，
  不能把“Action成功”当DB/归档也成功。Bot仍不直接触发消费者。

## 需要用户确认后才能继续的事项

1. 是否先实施A：正式模板本地预览（不发布、不写库）。
2. B的测试域名和独立部署目标；news.21min.com是否确为你拥有的域名。
3. C的隔离DB/Storage目标及备份/迁移权限；不共用生产发布指针。
4. D的切换日、旧writer停写与回退授权；需通过PR，不自动merge/main。
