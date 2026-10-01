# 一次性加密迁移授权（2026-10-01）

用户明确批准复用 news-v2 已有 KIDSNEWS_DISPATCH_TOKEN 到
grokbot-kidsnews 的 kidsnews-production environment。

只在 codex/relay-dispatch-20261001 分支运行一次临时 push workflow。
原 token 只进入 CI 环境变量，libsodium sealed box 使用目标 GitHub environment
公钥加密。artifact 只含 GitHub 可解密的密文和来源 run/commit，不含明文或摘要。
本机校验目标/key_id/源 commit 后，用维护者已有 gh 登录调用目标 secret PUT。
没有解密操作，不将 token 下载到 Mac/VM，也不触发网站流水线。

CI 仅 GET 两仓库 Actions 列表验证读取权限，不能把读取成功视为写权限证明；
原生产当日 dispatch 成功是现有用途的证据。若读取权限不足，记录阻碍，不扩大 scope。
完成后从分支删除临时 workflow/script，删除临时 artifact，关闭（不合并）PR。
保留本记录和 Atlas 交接，不改 main、生产内容、DB、archive 或邮件。

## 实际结果

临时 PR #87，不合并；CI run 36930276663（源提交
7afb4bb6c8ae064b196b58f934097a1272a02ece）成功。
本机只接收 sealed ciphertext；源 run/commit、目标仓库/environment 和实时
GitHub key_id 全部匹配后，目标 secret PUT 成功。
GitHub 已确认 KIDSNEWS_DISPATCH_TOKEN 于 2026-10-01T21:41:48Z 更新。
原 token 对 news-v2 和 kidsnews-v2 Actions 列表只读检查均 HTTP 200。
Python 3.10 假密钥测试：sealed roundtrip、无明文输出/文件、空值和换行拒绝；
workflow 分支/path/无生产命令与 Atlas JSON 检查通过。

本次清理提交已移除临时 workflow/script；只保留授权和结果记录。
正式模板视觉验收及真实 Bot 发布/回滚仍待验证，不把 secret 保存成功称为上线成功。
