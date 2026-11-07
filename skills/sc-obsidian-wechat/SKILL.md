---
name: sc-obsidian-wechat
description: 将 Obsidian Markdown 转换为微信公众号兼容的富文本，处理 Callout、Mermaid、代码高亮、链接脚注、图片、已发布公众号视频、封面和样式，并在用户明确要求时提交到微信公众号草稿箱。用户提到公众号排版、Obsidian 文章转微信、生成微信 HTML、上传公众号草稿或微信公众号发布时使用。
---

# SC: Obsidian 微信公众号发布

把 Obsidian 文章转换为适合微信公众号编辑器的内容，并可提交到草稿箱。始终使用随附脚本完成转换，不要手工重写 Markdown 转换逻辑。

## 工作边界

- 用户只要求排版或 HTML 时，使用 `--html-output`，不要创建草稿。
- 只有用户明确要求“发送到公众号”“上传草稿箱”或同义表达时，才创建公众号草稿。
- 本技能不执行正式群发；草稿生成后由用户在公众号后台预览、校对和发布。
- 默认不启用第三方 AI 封面。只有用户明确要求且本地配置已启用时，才允许脚本请求相应服务。
- 不显示、复制或记录 AppID、AppSecret、access token、AI API key。错误信息必须保留脚本的脱敏处理。

## 前置检查

1. 确认源文件是 UTF-8 Markdown，并读取 frontmatter。
2. 检查标题、摘要、作者、封面和正文图片是否齐全。
3. 检查视频：只接受 `wxv_` ID 或带 `vid=wxv_...` 的已发布公众号视频链接；本地视频和普通视频分享链接不能直接变成正文播放器。
4. 若要访问微信 API，确认配置文件存在。推荐路径：

```bash
mkdir -p ~/.config/sc-obsidian-wechat
cp config/wechat-credentials.example.md ~/.config/sc-obsidian-wechat/wechat-credentials.local.md
```

也可使用 `--config /path/to/wechat-credentials.local.md` 或 `SC_WECHAT_CONFIG`。

## 执行流程

以下命令均以本 `SKILL.md` 所在目录为工作目录；若当前目录不同，请使用技能目录下脚本的绝对路径。

### 只生成微信 HTML

此模式会上传正文图片到微信图片 CDN，但不会创建草稿：

```bash
scripts/publish.sh article.md --html-output article.wechat.html
```

### 创建公众号草稿

```bash
scripts/publish.sh article.md
```

指定主题：

```bash
scripts/publish.sh article.md --style deepblue
```

脚本依次处理 frontmatter、Obsidian 图片、Callout/Admonition、Mermaid、代码高亮、链接脚注、封面和草稿 API。任何图片或视频处理失败都应中止，不要发布缺少关键媒体的草稿。

## 验收

- 标题、作者、摘要和封面与源文一致。
- 图片已上传且顺序正确；Callout、列表、表格、代码块在移动端可读。
- Mermaid 已转成静态图片，不依赖 JavaScript。
- 普通链接已转脚注；公众号视频组件使用合法 `wxv_` ID。
- 脚本返回草稿 `media_id` 后，只报告“已进入草稿箱”，不要声称已经正式发布。

## 参考资料

- [样式主题](references/style-themes.md)
- [Callout 类型映射](references/admonition-mapping.md)
- [Mermaid 处理](references/mermaid-handling.md)
- [微信 API](references/wechat-api.md)
- [微信 CSS 兼容性](references/wechat-css-styles.md)
