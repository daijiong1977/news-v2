# 可替换的 AI / Agent 接入层

2026-09-30：用户计划最终将 Kids News 转入 Bot，也可能改用其他在线 Agent。
现有 ainew、poscast 已有 Supabase 访问；接入不以重新配置数据库权限为前提。

## 代码放在哪里

所有新模型通信代码放在 `pipeline/ai_providers/`。共同契约是
`CompletionProvider.complete(payload, timeout) -> chat-completion envelope`。
业务层保留提示词、编号排名、栏目分组、历史事件判断阈值、独立审核和发布校验。
Grok 品牌不写进业务函数，后续平台只需实现同一契约。

| 接入方式 | 实现 | 当前状态 |
| --- | --- | --- |
| DeepSeek / compatible HTTP API | `OpenAICompatibleProvider` | 已接入 `news_rss_core._deepseek_post`；重试、解析、DB provider 选择保持原行为 |
| Grok Bot 内置模型 / 其他在线 Agent | `AgentFilesProvider` | 文件交接适配器已实现、离线测试；尚未接入完整生产编排 |
| JEV 类型化评分 | `jev_prefilter.make_client`、`jev_rank` | 仍为现有实现；后续迁移须转换评分结构，不能假装为聊天模型调用 |

Grok Bot 是 Agent 运行脚本后读文件、作答，不存在本项目可直接调用的「Bot 内置 Grok API」。
如果未来使用真正的 Grok / Coze API，应新增各自适配器；不能把 Bot 订阅当 API key。

## 文件交接协议

调用者给 `AgentFilesProvider` 一个本次运行、日期、阶段专属目录，例如
`work/2026-10-01/run-001/review/`。完整 payload 的 SHA256 标识任务；目录内
`request.json` 包含材料、规则、请求 ID、答案文件路径和示例。
Agent 写 `answer.json`：

```json
{"request_id": "从 request.json 原样复制", "content": "{\"picks\":[1,2,3]}", "finish_reason": "stop"}
```

答案不存在、请求 ID 不符或交接格式错误时抛出 `AgentNeeded`。
调用者的 Agent CLI 捕获它、仅输出 `need.as_dict()`、退出 2；Bot 作答后重跑同一阶段。
格式报错最多改一次，仍失败则汇报。HTTP 网络错误沿现有异常路径处理。
同一任务复用有效答案，材料变更产生新 ID，不删旧答卷；请求原子写入可用于并发。
适配器只校验交接格式，文章 ID、字段结构、来源、字数、安全/中立等仍由业务校验器决定。
内置 Agent token 统计不可从答卷得知，返回空 usage，不编造费用。

## 后续完整迁移需要完成的工作

1. 新 Bot CLI 为排名、评分、改写和独立复核分别提供可恢复阶段；每个阶段保存输入和进度。
2. 把 JEV 的类型化评分映射成平台无关分数结构；阈值仍在代码中。独立全文审核使用单独的请求和阶段目录。
3. CLI 在业务 fallback 捕获异常之前处理 `AgentNeeded`。现有流水线有 fail-open 捕获，不能直接替换 transport 后声称完成迁移。
4. 首先跑测试内容，比较质量、时间和用量；确认后交给现有打包和 Supabase 发布路径。
5. 切换正式 routine 时保持一个生产生成者，并使用 ET 日期、run ID 和显式覆盖策略。

本次只建立通信边界。没有启用新 Bot routine、没有改变 Supabase 权限、没有关闭现有任务。
不会通过环境变量偷偷将生产流水线切入文件模式；完成可恢复编排后才接入该适配器。
