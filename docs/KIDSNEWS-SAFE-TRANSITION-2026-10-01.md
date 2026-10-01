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
用户随后明确测试域名为news.21mins.com（不是news.21min.com）。拼写已确认，
域名所有权、DNS现状与Vercel绑定仍需上线前只读核验，不能声称已配置。
计划将news.21mins.com绑定独立测试项目，kidsnews.21mins.com继续旧生产；先在
独立kidsnews-bot-shadow.vercel.app项目/预览URL验收正式模板。生产切换是换内容
生产者，不必重建网站/更换正式域名。现定时消费者目标白名单不含新测试域名，
不能直接指向它就往生产DB归档；B阶段不启用消费者，后续隔离配置另行评审。

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
2. 测试域名已确认news.21mins.com；仍需核对DNS/归属并确认独立部署目标和绑定权限。
3. C的隔离DB/Storage目标及备份/迁移权限；不共用生产发布指针。
4. D的切换日、旧writer停写与回退授权；需通过PR，不自动merge/main。

## 中午生成、人工验收、条件备用与回滚（用户新增方案）

目标：每天中午Bot先生成到news.21mins.com，满意才晋升正式站；不满意则保留
正式旧稿或触发旧生成。生成成功不是发布批准，测试预览不写生产历史/归档指针。

### 分两阶段，先复用早上版本作退路

当前旧Daily约06:10 ET运行，早于中午。因此初期不能声称“中午好了就取消当天
已跑过的生成”。试运行保持旧早上产物，Bot中午生成，满意后有审批地替换；
不好则不动正式站，直接保留当天早上的已核验包。这几天会双重生成但回退最稳。
观察合格后另行批准调度改造：旧生成改为条件备用，设截止时间（如13:00 ET，
仅建议未启用），批准新包则跳过旧生成；未批准/失败则人工或受控触发旧任务。
无批准不更新正式包，不把“没有人工回复”默认为质量认可。中午价格需实测，
不能把旧06:10成本估计当中午也同价。调度/触发生产工作流须另行授权。

### 发布与回滚版本，不覆盖唯一的成品

每次记录：内容package_id/ZIP哈希、run_date、正式reader/template SHA、生产Git提交/
Vercel部署ID、归档版本路径、该包的最终文章/搜索元数据快照、批准人与状态。
同日期保留多个不可变版本，至少保留当前正式、上一合格正式和当天早上fallback。
拟议release记录区分current/candidate/rollback，不把内容源started_at当回滚发布时间。
可在已有receipt模型扩展还是单独release表，需live schema核验后决定；本轮不建表。

发布顺序保持现有Action：批准→部署指定同包正式模板→公开哈希核验→ready→
定时消费者入库/归档→标正式一致。中途失败保留“待同步”并通知，不能声称跨
Git/Vercel/Storage/DB原子完成。锁/发布所有者确保新旧writer不抢写。

### 显式rollback任务（尚未实现）

1. 选一个已核验生产release并暂停当前发布队列/消费者的可冲突操作；确认目标日。
2. 恢复该release的正式reader+内容到站点（已有部署晋升/受控重部署或Git内容回退，
   具体按实际Vercel/Git链路验证；不强推main，不靠改DNS来回切）。
3. 公开核对payload/detail/image哈希，再恢复受影响日期/栏目的最终文章与搜索数据、
   当日归档/current指针/latest，其他日期不删除。模板和内容版本一起还原，避免错配。
4. 记录新rollback操作引用旧不可变包、新的操作时间、结果；任何一步失败可以续。

现消费者的superseded revision规则会拒绝旧包直接重发，Git回退网站也不会自动
恢复DB/归档。因此“一键rollback”需要显式授权的操作类型和定向恢复事务，不能
简单上传旧ZIP或改started_at绕过检查。publish/rollback应共用互斥控制。
来源cadence和曾使用日志不盲目倒退：记录实际发布/回退事件，再按有效发布策略
维护历史查询；不能抹掉真实调用/发布记录。七天查重只读当前有效发布事件，不混
未批准影子稿。阅读进度/积分/账号/家长数据不恢复整库；同日slot ID复用的阅读
记录兼容性也需专门验收。已发邮件无法撤回，邮件不参与自动重发/回滚。

### 验收与工期

必须模拟：部署成功DB失败、消费者中断、旧新任务竞争、同包重传、同日第二包、
缺栏包不误删、回滚后归档/搜索/历史一致、重复回滚幂等、个人阅读数据未变。
前端还原旧已部署版本通常较轻；**全链路一致的可恢复回滚**粗估另需1–2工作日
实现/故障注入，包含在C/D工作流中细化，不承诺现状已有一键按钮。
新增此需求后工程总量粗估4–6工作日+3–5天观察（依live schema/部署权限调整）。
最安全的第一步仍是A正式模板本地预览，然后B隔离站，不现在关闭生产06:10。
