# Obsidian companion article

## Placement

Use Obsidian CLI to list vaults and search for related notes, tags, or folders. Choose the existing subject folder that best matches the video's topic. Do not create a new top-level taxonomy for one article.

If no safe destination can be identified, write the draft under the project `outputs/` directory and ask the user where to move it.

## Frontmatter

Follow the vault's local convention. When no convention exists, use:

```yaml
---
title: "清晰、具体、面向读者收益的标题"
date: YYYY-MM-DD
source: "https://..."
tags:
  - 视频教程
  - 对应主题
status: draft
---
```

## 微信公众号结构

Write for readers who have not watched the source:

1. a short opening that states the problem and payoff;
2. what the tool/concept is and who it is for;
3. a step-by-step tutorial in the video's actual order;
4. small examples, commands, or screenshots where they remove ambiguity;
5. pitfalls and practical judgment learned from the demonstration;
6. a concise conclusion and next action;
7. source attribution.

Do not turn the transcript into a paragraph dump. Remove spoken repetition, restore missing context, and verify names and versions shown on screen.

## Images

Generate images only when requested. A useful package is:

- one 2.35:1 cover with safe central title space;
- one workflow diagram or conceptual illustration;
- two or three annotated source screenshots for concrete UI steps.

Prefer real screenshots for UI/code details and generated art for conceptual framing. Never generate fake screenshots of products. Keep assets beside the note or in the vault's established attachments directory. Use relative embeds such as `![[assets/example.png]]`.

## Final checks

- Every image path resolves.
- The title matches the actual tutorial/version.
- Claims are supported by the video or cited sources.
- Commands and code are copied from verified on-screen/source material.
- The article does not imply lip-sync or other processing that was not performed.
