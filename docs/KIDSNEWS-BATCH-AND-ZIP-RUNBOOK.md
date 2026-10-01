# Kids News 8→5→3：执行、ZIP 交接与启用边界

2026-09-30 ET；feature PR #86（共享代码）/ #1（Bot 导出快照），不是生产上线记录。

## 模型与代码职责

Python：来源/历史只读快照、URL/完全相同标题去重、公共网页按需取证、原文词数、
来源图片下载/解码/WebP、答卷/字数校验、状态锁与原子写、哈希、详情选项打乱、打包。
Grok：元数据搬栏/题材/同栏七天事件判断、重要性及趣味性、五选三、仅所选正文修稿并自检。
DeepSeek：每栏一次八选五+五篇正文；最终稿详情和逐字段/逐题详情复核。
正常三栏共 **3 次批量写稿 + 9 次详情 + 9 次详情复核**，原生任务约
**1 次计划 + 3 次选五选三 + 9 次修稿**。失败/补选另计；真实 Grok 周配额不能由此直接换算。
选五选三只附草稿和来源元数据，不重复附五份原文；修稿才附对应单篇原文。

绝不整组重新写：单篇长度异常由该篇 modifier 修；单篇结构异常只修该 ID。
整份 JSON 格式坏由原生 Agent 只修语法/恢复完整行，不再向 DeepSeek 发整组重写请求。
已有合格稿不重写，局部补稿不重新处理已满足的栏目；仍不合格换备用。
初始每栏最多八篇合格原文，每栏正文抓取预算独立为12（失败也计数，恢复不清零）；必要时沿用最多两轮/栏、每轮三 URL
的受限发现，新增来源只记建议，不启用来源表。预算耗尽可少于三篇并告警，不搬昨天成品。

图片与原文是按需共同资格单元：选中候选原页只访问一次，获取原文及图片元信息；
送 DeepSeek 前先检查/缓存图，最终打包复用缓存、核对哈希，不重复下载或做额外视觉 LLM。
图片机械合格不是视觉相关性或版权保证；重要 News 不因没有图直接淘汰。

## VM 完整真实影子测试（用户运行，不在 Mac 假装调用 Bot）

```sh
cd /workspace/kidsnews-shadow
git pull --ff-only origin codex/stepwise-full-shadow
.venv/bin/pip install -q -r pipeline/requirements.txt
```

从已有 Supabase 连接器只读取所有启用 `redesign_source_configs` 和 D-7≤日期<D 的
`redesign_stories`（archived=false），写 `work/D/batch-1/registry.json`，格式
`{"date":"D","sources":[...],"history":[...]}`。不含 key，不复制私人/家长数据。
新轮必须重取，不能沿用昨天 registry，也不能将影子标题当作已发布历史。
可选 `pipeline.registry_snapshot` 使用专用只读身份刷新；它不写数据库、不更新来源配置。
`DEEPSEEK_API_KEY` 已在 VM `.env`，不打印。下面用实际 D 替换占位符：

```sh
.venv/bin/python -m pipeline.agent_shadow prepare --date D --editor-mode autonomous --test-profile batch-deepseek --registry work/D/batch-1/registry.json --run-dir work/D/batch-1
.venv/bin/python -m pipeline.agent_shadow step --run-dir work/D/batch-1
```

一次一个 step：退出2按 JSON 指定路径写原生答卷后重跑；退出0继续下一步；
退出1停报真正工具/身份/锁/哈希错误，不反复重跑；done 后停止生成。

### 恢复合同（本次 B1–B7/S7 优先于原 Spec 的旧一小时限制）

- 所有 JSON 的 next/rerun 使用当前解释器绝对路径（VM 即 .venv/bin/python）。
  exit0完成一个单元，exit2按指定文件答题并在**同目录**继续，exit1暂停，exit3已完成。
- HTTP 有 response 的错误及可确认发送前连接失败记 failed_not_executed，单次命令最多
  三次传输尝试，受整轮120 HTTP调用预算限制；429读取Retry-After，上限120秒。
  修好身份后可同目录继续。读超时/发送后reset记outcome_uncertain，不自动HTTP重发。
- HTTP答卷是原子提交记录：answer.json含request_id、revision、attempt_id、usage、content、
  finish_reason。答卷匹配优先于attempting哨兵；provider-audit可从答卷/哨兵重建，不是唯一权威。
  第一次答卷保存在answer.attempt-1.json。禁止删状态、缓存或答卷，禁止整组重发/改完成答卷。
- 不再限制一小时wall-clock；任务120、HTTP120、各栏正文12的持久预算仍有效。
  超24小时用新只读registry加step --confirm-stale --registry；先重核同栏七天历史，
  duplicate/uncertain从候选和已接纳稿移除，日期不变。status不拿锁，answer_integrity列出异常。
- 只有缺篇数，或目录中有未尝试且可补重要News/不同Science出版方的稿，才扩大本栏。
  找不到可改善稿时保留安全正文并告警，不能为quota耗光其他栏目。News最高importance稿
  若被选入drafts必须排首位；否则用skipped:[{id,reason}]说明，不消费其余未选原文。
- 可选prepare --http-fallback native（默认关，input冻结）：仅传输失败用原生答题，
  单任务只兜底一次，原生批量4篇(3+1)、无8192 max_tokens；内容错误仍单篇修复。
  同一request_id和校验不变；native request隐藏运输字段，必须复制指定ID，不能自行重算。
  兜底计入MAX_TASKS并记fallback_tasks；work父目录的.http-fallback-runs.json检测连续两轮，
  连续兜底退出1要求查key/账户。uncertain兜底可能双重付费，必须报告。
- 兜底正文标记“同模型写稿并自检”；done/manifest provider=mixed；ZIP records带
  writer_provider。详情角色兜底也应报告，不把混合运行称全部DeepSeek或独立审核。
- 原文抓取证据与_fetch_audit同一次原子写入bodies.json；日志写失败不推翻已完成单元。
- 本轮只修影子。Review P1–P5均未实现：部分包删除风险、409/ready幂等、旧writer竞态、
  live schema及上线次序需影子通过后另开任务，不能凭离线绿灯开启生产消费者。
正文 modifier 用新会话/子 Agent，仅看本任务，返回修后稿和最终事实/安全/事件评分；
称“第二模型修稿并自检”，没有第三轮审核，不把自检称独立审稿。
不可修改已完成答卷、源代码或阈值；不部署、不入库、不发邮件。

```sh
.venv/bin/python -m pipeline.publication_bundle build --run-dir work/D/batch-1 --zip work/D/batch-1/publication.zip
.venv/bin/python -m pipeline.publication_bundle check --zip work/D/batch-1/publication.zip
```

默认是 shadow reader shell。保存 site、ZIP、metrics、provider-audit、editor-state、
candidate-images、review-results、detail-reviews 及脱敏日志。
报告 ET 起止、每栏8/5/3实际数量、抓取/图片次数、原生任务数、DeepSeek逐次usage/修正原因、
最终标题/来源/题材/重要性、拒稿及补选原因。没有 Grok 账单时说明未知，不估造3%达标。

## ZIP 合同与 Git 交接

ZIP 根目录直接是网站文件，不多套一层 `site/`，兼容现有 Action 的 unzip 行为：

- `payloads/articles_<category>_<easy|middle|cn>.json`；
- `article_payloads/payload_<date-category-slot>/<easy|middle>.json`；
- `article_images/*.webp`，以及原有 reader shell；
- `publication-manifest.json`：schema、date、run_id、counts、文件哈希、package_id、started_at、shell；
- `publication-records.json`：最终公开文章及修稿评分、原始来源标题/URL、实际来源配置 ID；
- `source-usage.json`：只列实际发布使用的配置 ID 和日期，无配置覆盖或任意 SQL。

这些 records 是公开文章元数据，不放原文全文、环境变量、答卷/私有日志、家长数据或凭据。
Python 重查最终正文词数/资格、跨阅读层 ID、图片可解码/尺寸及 SHA256、来源记录。
拒绝空包、路径穿越、重复文件、软链接、超限/ZIP bomb；20MiB压缩、80MiB展开、单文件5MiB、最多200文件。

正式网站必须显式提供**已核验的 kidsnews-v2 当前 reader shell**，不能用默认影子入口替代正式登录/归档页面：

```sh
.venv/bin/python -m pipeline.publication_bundle build --run-dir work/D/batch-1 --shell-dir /path/to/verified-kidsnews-v2/site --zip /new/path/publication.zip
.venv/bin/python -m pipeline.publication_bundle stage --zip /new/path/publication.zip --destination /new/path/git-stage
```

stage 只写新目录，不覆盖 checkout、不 commit/push；按 PR-first 流程将同一解包内容交给
`daijiong1977/kidsnews-v2` 的 `site/`，保留现有 Vercel/GitHub Action。仅 commit ZIP 不会让 Vercel读到网站。
**新生产发布需要另行确认目标、PR、当前 shell 和授权，测试不自动上线。**

## Bot 上传，定时函数处理（不改现有 GitHub Action）

私有 bucket：`kidsnews-publication-pending`。
Bot upload 到 `pending/<package_id>.zip`；公开网站与此包逐文件核验后，只上传
`pending/<package_id>.ready.json`（包哈希、ZIP哈希、site_url、verified_at）。
Bot **不调用** `finalize-news-publication`，也不直接 INSERT/UPDATE 文章库。
上传需要专用 uploader JWT + 项目 anon key；不能给 Bot service-role 写库权限。
现有 SELECT 连接器继续提供来源/历史，无需为它新增数据库写 key。

```sh
.venv/bin/python -m pipeline.publication_bundle upload --zip /new/path/publication.zip
.venv/bin/python -m pipeline.publication_bundle verify --zip /new/path/publication.zip --site-url https://kidsnews.21mins.com
```

环境变量仅在后续**已授权正式发布**时配置：`SUPABASE_URL`、`SUPABASE_ANON_KEY`（public）和
`SUPABASE_UPLOAD_TOKEN`（专用身份 JWT）。read-only helper 可用 `SUPABASE_READ_TOKEN`。
`.env` 不入 Git；token 到期先续专用身份，不通过 service-role绕过权限。
包/ready使用 immutable upload；重复409先下载比对，不开启无条件覆盖。

定时 worker 的次序：scheduler secret鉴权 → 全局lease → 扫描ready → ZIP/哈希/正文资格检查 →
再次核验公开网站 → 防止同日期旧revision覆盖 → 日期文件归档 → 再核验公开网站 →
**单事务**写 `redesign_runs` / `redesign_stories` / `redesign_search_index` 和实际使用来源轮换 →
兼容 `latest.zip` / 日期ZIP → archive-index最后 → done。
入库遵循当前 live schema，不照抄不兼容的四月 migration；没有 article/article_detail 新表要搬。
历史标题来自最终 `redesign_stories.source_title` / source_url，详情保存在日期 article_payloads，检索层三条/篇。
归档版本 `bot-versions/D/package_id.zip` 可恢复；日期平铺路径和30天 archive-index 与现有网站兼容。
只用 DB 的 cadence_days 计算 next_pickup_at，last_used_at不倒退；不写未用来源，不自动启用建议来源。

重复 run/package 的 DB receipt 幂等；DB已提交但归档索引失败，可继续同包，不二次插入。
index读取失败不得清空历史。跨 Storage/DB/网站**不是全局原子事务**，中断期间可能暂不同步，
done/索引最后写与重试用于恢复。旧生产 writer 不参加新worker的锁，仍可能覆盖站点/latest；
本次未禁旧writer、未改Action，worker会再次核验，不能保证两条生产链同时写时无竞态。

## 生产启用清单（本次没有执行）

1. 复核 live schema 并在隔离 Supabase 测试环境应用新 migration；注册专用 uploader 身份，
   添加到空的 `kidsnews_publication_uploaders` allow-list，验证仅能读/插入 ZIP/ready，不能写 done或业务表。
2. 部署专用函数时用 `--no-verify-jwt`，函数自行校验独立 scheduler secret。
   环境需要 `KIDSNEWS_PUBLICATION_SCHEDULER_SECRET` 和允许的正式 `KIDSNEWS_PUBLICATION_SITE_URL`；
   默认不开启；验收后才设 `KIDSNEWS_PUBLICATION_ENABLED=true`。
3. 在已确认时段配置 scheduler/pg_cron 调用，secret从 Vault取，不提交到代码。
   migration **不自动创建 cron**；明确现有生产 writer 的并行/回退安排。
4. 真实9篇审核、既有网站shell、Git PR及公开核验通过后才上传 ready，观察一次定时完成。

## 离线验证

Python3.10测试：`pipeline/test_agent_shadow_batch.py`、`test_batch_single_repair.py`、
`test_publication_bundle.py`，加原影子及生产纯函数回归。
Deno `bundle_test.ts` 测试 Python ZIP互通、公开核验失败零写、版本保护、索引失败恢复、幂等；
`sql_test.ts` 使用内存 PostgreSQL(PGlite)，执行真实 migration/RPC，验证9文章/27检索、
来源cadence、重放和事务回滚。它不是 live Supabase 集成测试。

```sh
python -m pytest -q pipeline/test_agent_shadow_batch.py pipeline/test_batch_single_repair.py pipeline/test_publication_bundle.py --basetemp=/tmp/NEW-UNUSED-DIR
KIDSNEWS_TEST_BUNDLE=/tmp/NEW-UNUSED-DIR/test_full_round_pack_upload_ve0/publication.zip deno test --allow-env --allow-read --allow-write supabase/functions/finalize-news-publication/bundle_test.ts supabase/functions/finalize-news-publication/sql_test.ts
```

记录明确区分：离线完整合同通过 / 真实模型内容通过 / 真实定时入库及公开部署通过。
