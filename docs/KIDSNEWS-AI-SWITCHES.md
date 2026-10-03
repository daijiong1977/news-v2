# AI 开关：逐阶段供应商（2026-10-03）

推荐新运行使用 `ai_stages`，未指定的阶段继承 `agent_provider`，
`repair` 默认继承 `review`。不要同时设置 `batch_writer`。

```json
{
  "agent_provider": {"type":"codex","model":"gpt-6.1-sol","reasoning":"medium"},
  "ai_stages": {
    "pickup": {"type":"codex","model":"gpt-6.1-sol","reasoning":"medium"},
    "batch_write": {"type":"deepseek","model":"deepseek-flash"},
    "selection": {"type":"codex","model":"gpt-6.1-sol","reasoning":"medium"},
    "review": {"type":"codex","model":"gpt-6.1-sol","reasoning":"medium"},
    "repair": {"type":"codex","model":"gpt-6.1-sol","reasoning":"medium"},
    "format_fix": {"type":"codex","model":"gpt-6.1-sol","reasoning":"medium"},
    "history_review": {"type":"codex","model":"gpt-6.1-sol","reasoning":"medium"}
  }
}
```

每个阶段都可以改为 DeepSeek/Grok/Codex/Claude 字符串或对象；模型由该供应商
实际账号支持情况决定。`pickup` 是摘要选题排序，`batch_write` 是批量初稿，
`selection` 是固定五选三顺序，`review` 是逐篇精修＋详情生成＋自检的一次任务，
`repair` 是正文/详情定点修正，`format_fix` 是准备答卷格式修复和选稿答卷修复，
`history_review` 是超过24小时恢复时的历史复核。不会新增独立详情审核调用。
Python 抓取、机械校验、部署及数据库步骤不是 AI 阶段，不配置供应商。

`ai-stages.json` 和逐阶段身份文件被冻结；恢复不能换配置、模型或身份。
全部供应商接口均为 JSON-in / JSON-out；CLI 也由 Python 包装，不手工交接。
配置只接受模型设置和环境变量名，拒绝明文 key；未知阶段名直接报错。
默认不存在自动供应商降级。下面的旧 `batch_writer` 配置保留兼容。

在运行 JSON 设置一个字段即可，无需改代码：

```json
{
  "all_ai": true,
  "agent_provider": {"type":"codex","model":"gpt-6.1-sol","reasoning":"medium"},
  "batch_writer": "deepseek"
}
```

`batch_writer` 允许 `deepseek` / `grok` / `codex` / `claude`。
默认模型分别为 deepseek-flash / grok-4.7-high / gpt-6.1-sol medium / sonnet。
可把字符串改为对象显式指定模型，例如
`"batch_writer":{"type":"deepseek","model":"deepseek-v4-pro"}`。
模型标识由当前账号服务提供；代码不猜升级型号。

此次只切三栏五篇初稿的批量写作。ID/摘要排序、五选三、精修、详情、自检、
必要格式修复依旧由 agent_provider 配置的 Codex medium 完成。
DeepSeek使用既有HTTP重试/答卷校验、JSON模式、16384输出上限、关闭thinking。
Grok用既有Cursor CLI适配，Codex和Claude用各自CLI适配；不使用Grok Bot。
所有接口都是给定JSON任务进、JSON答卷出，无网站/DB工具权限。
Claude没有工具/MCP/技能/项目settings和持久会话，业务密钥不进入其环境。

前提：DeepSeek需要环境变量DEEPSEEK_API_KEY，CLI需要安装且登录；密钥不写入配置。
切换仅对**新目录**生效；batch-writer.json、providers.json和答卷身份冻结。
同目录恢复不得换模型，不自动降级到另一模型、不清空缓存重跑整组。
没有batch_writer时保持旧模式兼容；已完成旧目录的标签和答卷不追溯。

Linux今晚配置：`/home/opc/.config/kidsnews/run-tonight.json`。
完整入口仍为 `.venv/bin/python -m pipeline.kidsnews_python --input-file <JSON>`。
配置不是定时器：不创建新cron，不擅自关闭旧定时。publish/database_archive按该轮
显式授权参数执行，模型开关自身不改变部署或数据库权限。

测试：离线Python3.10覆盖四选项路由、排序不受初稿模型切换影响、同目录禁换、
答卷缓存、Claude工具和业务密钥隔离、错误答卷停止。实际CLI认证只读检查与
真实文章质量/耗时验收分开；切换可用不代表四个模型都已跑过当日正式全轮。
