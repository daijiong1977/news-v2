# Kids News Agent 影子站

2026-09-30 用户同意先在另一 Vercel 网站影子运行，再迁移正式服务。

## 已建立的位置

| 项目 | 路径 / 发布位置 | 状态 |
| --- | --- | --- |
| 生成和共享接口仓库 | `daijiong1977/news-v2`；Mac `/Users/jiong/myprojects/news-v2-agent-provider` | 接口及影子站代码在 PR #86 |
| 影子阅读页面源码 | `shadow/site/` | 独立静态阅读页，无 Supabase 写入、登录或发信代码 |
| 测试内容导出器 | `pipeline/shadow_site.py` | 复用现有 v1 文章 payload，输出到全新目录 |
| Vercel 测试项目 | `kidsnews-bot-shadow`，scope `jiong-dais-projects` | 已创建，独立于 `kidsnews-v2` |
| 测试网站 | https://kidsnews-bot-shadow.vercel.app | 已核验 HTTP 200，尚无 Bot 文章 |
| 首次部署 | `dpl_7UUniYiNkJgPGzcZCbiytayPgg83` | 2026-09-30 13:33 EDT，READY |
| 正式网站 | https://kidsnews.21mins.com 和 https://news.6ray.com | 原生产流程继续运行 |

Vercel project ID `prj_wAKQb7C37whe0Wi6BNvb5zYpbceg`，team ID
`team_q9O2RWd2qc7ZkVNtas4naaed`；它们是项目标识，不是密钥。
本机 `shadow/site/.vercel/` 不入 Git。部署的是本地 PR 代码，不能把测试站上线说成 main 已合并。

## 如何放入真实测试结果

Bot 或其他在线 Agent 生成的结果先经共享内容校验，再使用已有 `emit_v1_shape`
输出 9 个栏目/阅读版本列表和逐篇 easy/middle 详情。影子导出器不生成或重审文章。

```sh
python -m pipeline.shadow_site --content-dir /path/to/generated-reader-output --date 2026-10-01 --provider grok-bot --output /tmp/kidsnews-shadow-run-2026-10-01
```

输出目录必须不存在。导出器验证日期、栏目、不同阅读版本 ID 一致、每栏最多三篇、
正文存在、本地图片路径；只复制引用到的内容，不复制 admin、parent、Supabase 配置或邮件工具。
零到两篇的栏目允许审阅，不补入旧日文章。`shadow-run.json` 保存日期、Agent 名称、栏目数量、
内容哈希和时间；审核状态默认 `unverified`，不能当作独立安全/中立审核已通过。
目录可用于任何 Agent，`provider` 仅标记来源，不决定模型。

授权的发布者在输出目录中明确关联测试项目，然后部署：

```sh
vercel link --yes --project kidsnews-bot-shadow --scope jiong-dais-projects
vercel deploy --prod --yes --scope jiong-dais-projects
```

这里 `--prod` 只更新 **kidsnews-bot-shadow 的稳定测试地址**。部署前检查该目录
`.vercel/project.json` 的 projectName 和 projectId 与上表一致。不要从 `kidsnews-v2`
目录运行上述命令，不要复用正式项目 `.vercel` 链接或正式 Supabase `latest.zip`。
Bot 现有 Supabase 权限可以继续使用；此阶段不需要新密钥或数据库改动。

## 比较与切换

先接入 Agent 的可恢复排名、改写、独立复核步骤，影子输出由上述导出器发布。
每天比较正式站和影子站的选文重要性、分类、来源、七天同栏事件重复、中文及英文中立性、
儿童安全、字数、补稿原因、步骤耗时和模型用量。平台相关交接只放在 `pipeline/ai_providers/`。

目前只完成站点和导出接口，完整 Bot 流程、新 Bot repo、VM 安装和 routine 尚未建立。
真实结果连续验证后再安排生产切换，保持同一时间只有一个生产生成者。
网站 `noindex` 避免搜索索引，但测试地址是公开阅读地址，不适合私密材料。
