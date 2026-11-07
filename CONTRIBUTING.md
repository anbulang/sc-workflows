# Contributing

欢迎提交 issue 或 pull request。

## 原则

- 每个 skill 聚焦一个可识别的用户目标，不把个人案例写成普遍规则。
- 不提交真实客户资料、未公开业务数据、媒体成片、模型权重、账号凭据或绝对用户路径。
- 新增脚本必须有明确复用价值，并提供最小可运行测试。
- skill 显示名使用 `SC: ` 前缀，技术名和目录名使用 `sc-` 前缀。
- 保持对源文件的保护、外部写入授权和付费服务确认边界。

## 提交前

```bash
python3 tools/validate_plugin.py
python3 -m unittest discover -s tests -v
```

若修改版本或插件说明，请同步更新根目录 `plugin.json` 与 `.codex-plugin/plugin.json`。
