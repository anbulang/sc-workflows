---
name: sc-video-subtitle-editor
description: >
  先分析本地视频的语言、结构、画面、说话方式和主题，再自适应完成语音转录、字幕制作、
  内容校对、静音/口头语候选剪辑、时间轴重映射、软字幕封装或字幕烧录。适用于课程、讲座、
  访谈、会议、演示、教程、口播、Vlog、屏幕录制等含语音的视频；当用户提到视频转录、
  字幕生成或校对、去口水词、静音剪辑、字幕对齐、字幕烧录时使用。
---

# 通用视频转录、剪辑与字幕

先分析视频，再决定工作流。不要从文件名、用户身份或既往案例推断它一定是课程、讲座、
PPT、中文或包含古文；这些都必须由视频、音频、转录或用户资料提供证据。

## 核心原则

1. 保留原片，所有中间文件和成片使用新路径。
2. 把“识别候选”和“批准剪掉”分开。任何会改变表达节奏或含义的剪辑都先让用户确认。
3. 只在缺依赖时读取 [environment.md](references/environment.md)，安装或编译前先获得用户许可。
4. 需要剪辑时读取 [editing-guardrails.md](references/editing-guardrails.md)。
5. 发现大量画面文字、专名、引用或领域术语时，读取
   [content-analysis-and-proofreading.md](references/content-analysis-and-proofreading.md)。
6. 长时间转录和编码放到后台，使用当前环境支持的轮询/等待机制汇报进度，不要阻塞等待。

## 交付模式

根据用户目标选择一项或组合，不要默认一定要剪辑或烧录：

- 仅转录：原始转录、SRT/VTT 或纯文本。
- 字幕校对：校对后的旁挂字幕，不改视频。
- 清理剪辑：剪掉已批准片段，附重新对齐的字幕。
- 软字幕：将字幕作为可开关轨道封装进视频。
- 硬字幕：把字幕烧进画面。

如果用户已明确交付物，直接执行；只有输出形式或剪辑尺度会实质改变结果时才询问。

## 步骤 0：建立内容画像

在完整转录和剪辑前，先检查媒体信息、音频和代表画面：

1. 用 `ffprobe` 获取时长、分辨率、帧率、音轨、声道和字幕轨。
2. 从开头、中段、结尾及若干均匀时间点抽取 6–12 张代表帧并读图；需要场景感知抽帧时运行：

   ```bash
   bash scripts/extract_scene_frames.sh input.mp4 analysis_frames/ 0.3
   ```

3. 试听或先转录 30–90 秒的多个样本，覆盖开头、主体和结尾；不要只分析片头。
4. 形成简短画像并据此制定流程：

   - `languages`：主要语言、夹杂语言、是否需要双语字幕。
   - `format`：单人口播、多人访谈、会议、屏幕录制、幻灯片、实拍、表演或混合。
   - `visual_evidence`：画面是否有标题、姓名条、术语、代码、产品界面、引用或其他可校对文字。
   - `audio`：说话人数、重叠说话、噪声、音乐、长停顿、语速和收音质量。
   - `subject`：从内容识别出的领域、专名、人物、作品、机构、产品和可能的引用来源。
   - `edit_risk`：哪些停顿或口头语可能是表达、表演、演示操作或对话节奏的一部分。
   - `plan`：转录语言/模型、候选剪辑规则、校对证据和交付物。

不要问用户“这是不是教授课程”之类能从视频判断的问题。无法可靠判断的字段标为“不确定”，
只向用户确认会影响最终结果的选择。

### 按内容切换策略

- 单人口播或演讲：可以检测静音和孤立口头语，但仍先给用户看候选和上下文。
- 多人访谈/会议：保留轮次间停顿和应答词；重叠说话附近不要自动剪。
- 教程/演示/屏幕操作：停顿可能对应操作步骤，必须结合画面判断。
- 表演、剧情、音乐或强节奏内容：默认只做转录/字幕；除非用户明确授权，不运行口头语清理。
- 有画面文字：把画面当作拼写与专名证据，但不能把屏幕文案当逐字稿改写说话内容。
- 有引用、数据或领域术语：按识别出的主题寻找可靠来源核验；不要预设只校对某一类经典文本。

## 步骤 1：准备环境与转录

依赖和模型选择见 [environment.md](references/environment.md)。先提取单声道 16 kHz PCM 音频：

```bash
ffmpeg -y -i input.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 audio.wav
```

先用内容画像选择语言。语言明确时传对应代码；多语言或仍不确定时用自动检测，不要固定成中文：

```bash
MODEL=$(bash scripts/pick_whisper_model.sh)
whisper-cli -m "$MODEL" -f audio.wav -l "$LANG" \
  -t "$THREADS" -osrt -oj -ojf -sow -pp -of transcript
```

保留 `-ojf` 逐词时间戳；后续候选检测、剪辑和字幕对齐都依赖它。检查转录是否覆盖完整时长，
并抽查开头、中段、结尾的语言识别和时间戳。

## 步骤 2：生成剪辑候选

只有用户需要清理剪辑时才运行：

```bash
DURATION=$(ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 input.mp4)
python3 scripts/find_edit_candidates.py transcript.json candidates.json \
  --duration-seconds "$DURATION" --language "$LANG"
```

脚本输出三类候选：

- `long_silence`：长静音。是否可剪由内容画像决定，不是普遍安全项。
- `filler_word`：当前语言词表中的孤立口头语。只在语境确认无语义时考虑剪。
- `repeat_candidate`：连续重复。永远是高风险复核项，不得自动剪。

对不在内置词表中的语言，脚本只检测静音和重复；可用重复的 `--filler` 参数显式补充经用户认可的词。
展示每条候选的时间、文本及前后文，抽样播放高频类别。让用户确认开头/结尾、静音、口头语和
重复项分别如何处理，再生成 `approved_cuts.json`。不要按类别直接全选。

## 步骤 3：剪辑并生成保留时间段

先读取 [editing-guardrails.md](references/editing-guardrails.md)，然后运行：

```bash
python3 scripts/build_edl.py approved_cuts.json "$DURATION" keep_segments.json
```

脚本会把剪切区间取补集，并打印 `select`/`aselect` 表达式。对恒定帧率视频可一次性重编码：

```bash
ffmpeg -y -i input.mp4 \
  -vf "select='between(t,S1,E1)+between(t,S2,E2)+...',setpts=N/FRAME_RATE/TB" \
  -af "aselect='between(t,S1,E1)+between(t,S2,E2)+...',asetpts=N/SR/TB" \
  -c:v libx264 -preset medium -crf 18 -c:a aac -b:a 192k edited.mp4
```

剪切点通常不在关键帧上，不能使用 `-c copy`。可变帧率、长 GOP、多人重叠或需要帧精度时，
按 guardrails 中的建议改用分段 `trim/atrim + concat` 或先规范帧率。

## 步骤 4：重映射并校对字幕

有剪辑时重映射原始 SRT：

```bash
python3 scripts/retime_srt.py transcript.srt keep_segments.json final_subtitles.srt
```

然后完成全文校对，不能只检查“看起来重要”的片段：

1. 忠实于实际说出口的内容；不要擅自润色、补句或把口语改成书面文案。
2. 优先用同时间轴上的清晰画面文字确认姓名、标题、术语和专名。
3. 再用用户资料、检测出的来源和可靠外部来源核验引用、数字与领域术语。
4. 通读全文寻找系统性同音/近音错误，并把已确认词表应用到其他出现位置。
5. 对剪掉的 `filler_word`，同步从对应字幕条中删除该词；`retime_srt.py` 只改时间，不改文字。
6. 没有可靠证据的地方不要猜；列出时间戳、原文和疑点交给用户。

当画面文字较多或需要资料核验时，按
[content-analysis-and-proofreading.md](references/content-analysis-and-proofreading.md) 执行。
中低置信度修改逐条确认；已获得统一授权的高置信度拼写修正可批量应用，但要保留修改清单。

## 步骤 5：封装或烧录字幕

根据交付模式选择旁挂、软字幕或硬字幕。硬字幕示例：

```bash
ffmpeg -y -i edited.mp4 \
  -vf "subtitles=final_subtitles.srt:force_style='FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,MarginV=30'" \
  -c:v libx264 -preset medium -crf 18 -c:a copy output_with_subs.mp4
```

根据横屏/竖屏、分辨率、安全区、画面已有文字和语言字体调整样式。先确认字体覆盖所需字符。
路径含空格、中文或冒号时，在纯 ASCII 临时目录中使用简短文件名运行 `subtitles` 滤镜。

若合并剪辑与烧录，字幕滤镜必须位于 `select,setpts` 之后，因为字幕使用剪辑后的时间轴。

## 步骤 6：质量验收

交付前至少检查：

- 原片仍存在，所有输出路径不同于输入。
- 成片时长约等于原时长减去批准剪切总时长。
- 每个剪切点前后没有吞字、爆音、跳帧或误删动作；高风险剪切逐点试听/查看。
- 字幕在开头、中段、结尾以及每个剪切点之后仍同步。
- 全文没有明显专名、数字、同音字和被删口头语残留；存疑项已单列。
- 字幕不挡关键 UI、姓名条或画面文字，竖屏和横屏均在安全区内。
- 用 `ffprobe` 确认视频流、音轨、字幕轨和时长符合交付模式，并实际播放抽查成片。

汇报最终文件、修改摘要、剪掉的总时长、校对依据、未解决疑点和可复现的中间文件。
