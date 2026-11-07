# SC Workflows

面向中文创作者的 Codex 视频工作流插件，当前包含两个可独立触发的 skill：

- `SC: 视频字幕剪辑`：分析视频语言、结构、画面和说话方式，自适应完成转录、剪辑候选、字幕校对、时间轴重映射与字幕交付。
- `SC: 视频中文化与文章发布`：把英文视频制作成自然中文配音、中文字幕和屏幕感知剪辑版本，并可生成 Obsidian/微信公众号配套文章。

插件采用 OpenAI 推荐的可移植 `plugin.json + skills/` 结构，同时保留 `.codex-plugin/plugin.json` 兼容清单。它不包含模型、媒体文件、账号凭据或遥测代码。

## 安装

从 GitHub 添加 marketplace：

```bash
codex plugin marketplace add anbulang/sc-workflows
```

然后重启 ChatGPT/Codex 桌面端，在 Plugins Directory 的 `SC Workflows` 来源中安装 `SC: Video Workflows`。

也可以克隆后从本地目录测试：

```bash
git clone https://github.com/anbulang/sc-workflows.git
codex plugin marketplace add ./sc-workflows
```

## 使用示例

```text
使用 $sc-video-subtitle-editor 分析这个视频，生成校对后的中文字幕，并列出需要我确认的剪辑候选。
```

```text
使用 $sc-localize-video-publish 把这个英文教程制作成中文配音、中文字幕和 60fps 成片，并编写配套文章。
```

## 运行依赖

基础环境：

- Python 3.10+
- FFmpeg 与 FFprobe
- Bash（字幕剪辑中的辅助脚本）

按任务选装：

- `numpy`：语速与画面变化分析，安装见 `requirements.txt`
- `whisper.cpp`：本地语音转录
- `yt-dlp`：公共视频 URL 下载
- 支持目标语言的本地 TTS/声音克隆引擎：插件不绑定或下载具体模型
- Obsidian CLI：把文章直接写入 Obsidian；未安装时可先输出普通 Markdown

安装 Python 依赖：

```bash
python3 -m pip install -r requirements.txt
```

## 安全与隐私

- 原片默认保留，输出使用新路径。
- 剪辑候选不等于批准；会改变表达或画面的删除需要用户确认或明确授权。
- 声音克隆前应确认拥有使用该声音的授权。
- 默认不调用付费 TTS、翻译或口型服务。
- 插件本身不上传媒体、不收集数据，也不携带 API key、Cookie 或模型权重。

## 开发与验证

```bash
python3 tools/validate_plugin.py
python3 -m unittest discover -s tests -v
```

验证器会检查 manifest、skill frontmatter、相对链接、Python/Bash 语法、敏感路径和异常大文件。

插件格式参考 [OpenAI Plugins 文档](https://developers.openai.com/plugins/build/plugins)。

## 许可证

[MIT](LICENSE)
