# Security Policy

## Reporting

请不要在公开 issue 中粘贴 API key、Cookie、账号信息、未公开媒体或客户材料。安全问题可通过 GitHub Security Advisory 私下报告。

## Scope

本仓库只提供工作流说明和本地辅助脚本，不托管服务、不收集遥测，也不包含模型权重。执行下载、转录、TTS、FFmpeg 或 Obsidian 操作时，仍应遵守对应工具、内容来源和数据存储位置的安全要求。

微信公众号 AppSecret、access token 和 AI 生图 API key 只能保存在本地 `wechat-credentials.local.md` 或用户配置目录中。仓库忽略 `*.local.md`；发布脚本会脱敏常见凭据字段，但仍不应把完整运行日志连同私密文章发布到公开 issue。
