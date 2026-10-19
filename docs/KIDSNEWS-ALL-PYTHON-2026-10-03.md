# Kids News 全 Python 执行入口（2026-10-03）

入口：`python -m pipeline.kidsnews_python`。标准输入一个 JSON，标准输出一个 JSON；
不依赖 Grok Bot 对话、Edge Function、Mac 路径或人工 request/answer 文件交接。
Python 3.10+；Mac/Linux 均可。旧三阶段入口、生产 full_round 和原网站 Action 不改。

## 模型边界

第一部分仍由现有 Python 抓正文/图、机械过滤、DeepSeek Pro 摘要排序、Flash 五稿。
第二部分由 Python 通过 completion 接口调用 Agent/Grok：每栏一次固定五篇排序；
每篇一次精修、两级详情与自检，Python 校验，最多按旧规则定点修复/省略详情。
同一事件/同栏七天历史重复、儿童安全、结构/哈希仍不可放宽。最多尝试固定五篇，
成功三篇后停止；五篇全部不能满足硬门禁则报告失败，不编文章凑数。
第三部分 Python 打包正式 reader，走现有 GitHub Action，核验网站，显式开启时再
继续备份→日期归档→自动成对 SQL→数据库→验收。网站成功不是全链路成功。

默认 provider 为本机已登录的 Cursor CLI `agent -p --mode ask --output-format json`，
默认模型 grok-4.7-low，可用 KIDSNEWS_AGENT_MODEL 覆盖。CLI 不是 HTTP API；
`pipeline.cursor_json` 将其包装为 messages JSON 输入、completion JSON 输出。
Cursor 本身须安装/登录；Linux 并不会继承 Mac 登录。可以使用 CURSOR_API_KEY。
没有 force/yolo、续聊或仓库 workspace；任务材料通过 stdin 传入空临时目录。
子进程仅继承基本环境和 CURSOR_*，不继承 DB/Storage/DeepSeek 密钥。
这是 read-only 运行模式与权限隔离，不宣称提示词本身等于安全沙箱。

亦可指定 `agent_provider`：

```json
{"type":"http","endpoint":"https://your-agent.example/chat/completions",
 "model":"your-grok-model","key_env":"AGENT_API_KEY"}
```

这是 OpenAI-compatible completion 协议，不假定任何 Cursor 私有 HTTP 接口。
直接 HTTP 需要自己的 key/费用；Cursor subscription 不等于 xAI API 额度。
模型用量记录在 api-tasks/*/*/answer.json，未知即空对象，不造账单。
Cursor 启动/系统上下文有开销；此次纯 JSON 连通小测约 7 秒、返回 inputTokens
22,200/outputTokens 74，不将这些数字误当文章流水线成本或纯业务 prompt 大小。

## 安装与本地生成

```sh
python3 -m venv .venv
.venv/bin/pip install -r pipeline/requirements-publication.txt
.venv/bin/python -m pipeline.kidsnews_python --input-file run.json
```

`run.json`（路径按实际平台填写）：

```json
{"operation":"run","date":"2026-10-03","run_dir":"/private-runs/2026-10-03/test-1",
 "model":"grok-4.7-low","publish":false,"database_archive":false}
```

只生成 ZIP，不上线。可传 `registry` 指向来源/七天历史 JSON；未传时 Python 用
SUPABASE_READ_TOKEN（缺省 SUPABASE_SERVICE_KEY）分页只读抓取、冻结 registry。
空历史/无权限拒绝，不能当作不存在历史。来源和候选沿已有十二→五→三规则。
正常需 DEEPSEEK_API_KEY，以及 Cursor login/鉴权。模板下载/交付沿现有 git 工具。
可显式传 `env_file` 指向本机私有 `.env`（只读、不覆盖已导出的环境）；不自动猜路径，
不打印密钥，不把密钥写进 run.json。启用后端时先只读检查四表可访问，失败在模型/
网站操作之前停止；REST 的 GET 不能证明写权限，实际写入必须逐项读回验收。

## 发布并接续数据库/归档

在 Bot snapshot 仓库运行，保留已有发布审批与 Action 环境保护：

```json
{"operation":"run","date":"2026-10-03","run_dir":"/private-runs/2026-10-03/live-1",
 "model":"grok-4.7-low","publish":true,"database_archive":true,"execute":true,
 "ack_same_day_replacement":true,"branch":"codex/website-release-2026-10-03-python-1",
 "state_dir":"/private-backups/2026-10-03-python-1"}
```

网站-only 仍可 database_archive:false。现有 CI 保管 latest 上传及 dispatch 凭据；
默认 database_transport=rest：复用原流水线 SUPABASE_URL + SUPABASE_SERVICE_KEY，
经 Supabase Data API 做 insert/update/upsert/delete；Storage 复用同一个 service-role key。
不需要新增 token、不需要 KIDSNEWS_DATABASE_URL、不调用 Edge Function/RPC 或部署 schema。
此次已确认原 news-v2/.env 的凭据为 service_role，四张表只读 HTTP 200；密钥未输出、
未复制到 Git/答卷。VM 使用其既有私有环境；本机可显式 env_file 指向原项目私有 .env。

显式 database_transport=postgres 才需要 KIDSNEWS_DATABASE_URL（专用数据库账号、TLS）。
此可选 adapter 不需要 Supabase 账号管理 token。**此代码不配置数据库密码或账号**；
service-role JWT 不是 PostgreSQL 密码，不能混用。以下权限/5432要求只适用于 postgres：
必须直连或 session pooler 的 5432 端口；拒绝 6543 transaction pooler，防止会话锁失效。
连接方式依据 [Supabase 官方连接文档](https://supabase.com/docs/guides/database/connecting-to-postgres)。
DB role 需四张业务表的 SELECT/INSERT/UPDATE/DELETE 和锁权限；精确 SQL 回滚
临时禁用既有 search trigger，需该表所有者权限，因此最小权限角色方案必须先审查，
不能声称普通只读/service-role 默认满足。连接URL放私有环境，不放 JSON/Git/Agent。
首次启用还应核验 schema/trigger、实际角色权限与单独备份；不能把离线测试说成部署。

## 后端执行顺序与恢复

1. 核验 latest manifest 与本包相同、网站 reader 全文件 hash 一致。
2. 本机私有状态目录锁防同目录并发。REST 无远端跨机器锁；仅可选 postgres 使用
   session advisory lock。首次运行必须避开旧生产及另一台机器同日期写入。
3. 同一份 artifact 冻结数据库旧值与 apply/rollback SQL；备份每个将替换的归档对象，
   全部落盘并 hash 校验后才允许写入。备份目录 0700、文件 0600，不能在 repo/work。
4. 写原结构的 `<date>/payloads`、`article_payloads`、`article_images`、`<date>.zip`
   和日期 manifest。日期缺失时保留其他日期更新 index；不写 latest、不删除孤儿旧文件。
5. 每次写前记录 attempting，读回 hash 成功标 complete。失败恢复只读回，不盲重发。
6. 归档全部验证，再核验网站未被替换。默认 REST 按 runs→stories→search→sources
   更新四表，保留 UUID/阅读进度，已有行仅 PATCH 改变字段，新行 conflict-ignore 不覆盖
   并发新插入；每行写前 sentinel、写后读回，rest-execution.json 记录断点。
   apply/rollback SQL 仍自动生成冻结作为审计/可选 SQL 方式，但 REST 不执行任意 SQL。
   可选 postgres 则在短 SQL transaction 中完成四表更新。
7. DB 原值/新值 guard、DB读回、归档读回、网站读回全部通过才 status:complete。

同目录重跑复用原稿、API 答卷、SQL、Storage before-images，成功操作不重复。
网络响应丢失：归档/REST 行读回等于目标值可继续，不再发送该写请求；REST sentinel
仍在而目标没到则停止人工核对，不能盲重发。SQL attempting 同样停止人工核对。
源/已接受答卷/provider 更改、备份污染、第三方写入会停止。超过24小时沿旧 stale 门禁，
不静默改日期；需显式 `confirm_stale:true` 才以当前 ET 日期重读历史、逐栏 API 查重。
新历史里的重复/不确定项不能使用；若已接受稿变成重复，停止，不篡改旧成品。
保留 debug，不清理状态文件。

REST 四表不是一个事务，快照也是四次只读请求；中断可能暂时部分完成，恢复必须
复用原 before/after 和逐行日志。没有远端锁或严格 CAS，不承诺跨写入者原子性。
Storage 与数据库更无跨系统原子事务；即使 postgres session lock 也只覆盖本模块参与者，
旧生产写入者不一定持有。首次 live 选无其他 writer 并发时段；整体前像检查、逐行
再次检查和验收能检测多数冲突，但不等于消除最后一次检查与写入之间的竞争窗口。
失败不会自动覆盖回网站；保留明确阶段，修复后原目录继续或执行限定回滚。

已有验证网站可单独补后端：

```json
{"operation":"backfill","artifact_dir":"/path/reader-artifact",
 "state_dir":"/private-backups/release-id","execute":true}
```

数据库与日期归档回滚（不回滚网站/latest）：

```json
{"operation":"rollback","state_dir":"/private-backups/release-id","execute":true}
```

先整体核对归档没有第三方改动，再按原 before/after 回滚 DB（REST 来源→search→
stories→runs；只删除本批新增行，搜索派生 tsv/更新时间由数据库重新生成，不禁用触发器），
最后恢复旧对象/只删除本操作新建对象。postgres 则使用原 rollback.sql 精确回滚。
两边中断仍保留状态；SQL结果不确定时拒绝盲回滚。网站 rollback 仍用现有
CI 原备份机制；不将 DB/archive 回滚标记成全站回滚。这里是涉及范围备份，不是 full dump。

## 测试与部署边界

新增离线测试：真实 completion envelope/环境隔离、固定五选三/九稿/无交接及恢复、
模型超时防重复、归档备份先于上传/污染检查/响应丢失/精确回滚、后端执行顺序与
幂等、发布审批先于写入、Postgres TLS/project 限定。原有 Python3.10 套件照跑。
本机 Cursor 连通测试是实际模型调用；文章生成、数据库、Storage、部署仍未进行
新的真实端到端操作。旧 Edge worker/migration 不部署、不启用、不调用。

验证：Python 3.10 原相关套件 350 项通过；追加只读数据库权限门禁后，新入口
专项 19 项通过。Bot 导出后重跑含该新增用例的完整 351 项套件。
2026-10-03 同日追加 REST 兼容：新增六项测试覆盖完整恢复/回滚、响应丢失不重复写、
不确定未写入停止、外部改动拦截、凭据/项目/冲突保护以及无需数据库密码的默认入口。
含 REST 的完整 Python 3.10 相关套件：357 项通过，两个既有警告；未真实写库/部署。
