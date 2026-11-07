---
name: sc-localize-video-publish
description: End-to-end workflow for downloading a public English video or accepting a local source, translating it into natural Chinese, generating local same-speaker-style Chinese dubbing, editing the video around the Chinese delivery without losing unique on-screen information, creating synchronized Chinese subtitles, preserving source resolution and frame rate, validating the final media, and writing a companion Obsidian article. Use for X, YouTube, lecture, tutorial, screencast, or talking-head localization requests, especially when the user wants a no-paid-service workflow, dynamic pacing, 60 fps preservation, or an Obsidian/微信公众号 draft. Do not use for lip-sync unless the user explicitly requests it.
---

# SC: 视频中文化与文章发布

## Goal

Produce one polished Chinese-localized master and its publication materials from an English video. Keep the speaker's recognizable delivery pattern, protect unique visual information, avoid paid services by default, and preserve the original source.

## Non-negotiable defaults

- Preserve the downloaded/original source and never overwrite it.
- Use local tools and already available models. Do not submit to a paid API or lip-sync service without explicit approval.
- Do not lip-sync by default. The accepted baseline is Chinese dubbing, synchronized subtitles, and screen-aware editing.
- Preserve source resolution and frame rate; for a 60 fps source, deliver 60 fps.
- Use one shared edit timeline for video, audio, subtitles, reports, and article timestamps.
- Keep natural variation in pace. Do not force every Chinese sentence to an identical speed or to the exact English duration.
- Cut redundant holds, waits, and repeated states first. Never remove unique code, UI transitions, results, diagrams, or other key information unless the same information remains clearly visible before or after the cut.
- Deliver soft Chinese subtitles plus an external UTF-8 SRT. Burn subtitles only when the user asks.
- Retain only approved deliverables after acceptance; delete obsolete renders and rebuildable intermediates only after a whitelist review.

## Companion capabilities

- Use the bundled `$sc-video-subtitle-editor` for transcription, subtitle, and time-remapping mechanics when relevant.
- For public URLs, use an installed media downloader capability when available; otherwise use `yt-dlp` directly.
- When Obsidian CLI/Markdown capabilities are installed, use them to locate the vault and write the article. Otherwise produce a portable Markdown draft under the project output.
- Use image generation only when the user asks for a cover or article illustrations.
- The workflow requires FFmpeg/FFprobe and Python. Pacing and visual analysis scripts also require NumPy. A multilingual local TTS engine is optional and is not bundled with this plugin.

## Workflow

### 1. Establish the project and preserve provenance

Create `source/`, `work/`, `outputs/`, and `reports/` under a project folder. Record the source URL, download time, source filename, and the user's stated authorization. Download the best available video/audio without recompressing. Probe it with `ffprobe` and save duration, dimensions, frame rate, audio layout, and stream metadata.

Read [workflow.md](references/workflow.md) before starting a new project. Use its approval gates and retention rules.

### 2. Transcribe and translate

Prefer trustworthy source captions; otherwise transcribe locally. Split the English transcript into complete semantic units, then group adjacent sentences into dubbing tracks that can be spoken naturally.

Translate for speech, not word-for-word alignment:

- preserve product names, commands, code identifiers, version numbers, and causality;
- shorten repetition and filler while preserving meaning;
- make demonstratives explicit when the screen supplies context;
- keep each subtitle readable and each dubbing group semantically complete;
- maintain a bilingual segment JSON and a track JSON using [schemas.md](references/schemas.md).

### 3. Generate a voice sample before a long render

Extract a clean 10–30 second voice reference with little music or overlap. Use an available local multilingual voice-cloning TTS engine. Generate sentence/group WAV files at 48 kHz mono PCM16.

If the voice or translation style has not already been approved, first produce a 60–90 second sample containing a clear face and continuous speech. Include Chinese audio and subtitles; omit lip-sync. Continue to the complete video only after the sample is accepted.

### 4. Preserve delivery dynamics

Extract the original English speech to mono PCM16. Run:

```bash
python3 scripts/analyze_pacing.py original_english_mono.wav tracks.json segments.json tempo_plan.json
python3 scripts/apply_tempo.py tempo_plan.json natural_takes dynamic_takes duration_report.json
```

The analyzer derives modest changes from local speech density and vocal energy. Typical bounds are `0.92–1.08x`, with adjacent changes no larger than `0.06`. Adjust the bounds only when listening proves a wider range is necessary. Use FFmpeg `atempo` so pitch is preserved.

Treat tempo as an expressive cue, not a hard synchronization constraint. Prefer this order:

1. natural Chinese wording;
2. small dynamic tempo changes;
3. removal of visually redundant time;
4. a short natural pause or a very small visual hold.

Never solve a large timing mismatch with long inserted silence or obviously accelerated/slowed speech.

### 5. Analyze and edit the picture

Exclude the speaker picture-in-picture region when measuring screen changes. Example:

```bash
python3 scripts/analyze_visuals.py source.mp4 visual_metrics.json \
  --crop 1440:1080:0:0 --fps 5
```

Build a cut plan in source time. Protect transcript boundaries and all detected UI/code changes. Candidate cuts should begin and end on visually matching states. Then perform semantic review with contact sheets or extracted frames around every proposed cut.

Classify each cut as:

- `screen_state_match`: a repeated/static state with matching endpoints;
- `semantic_review`: a reviewed talking-head pause, redundant wait, or transition whose information survives on adjacent frames.

Reject a cut if a unique command, code line, click result, UI state, diagram step, or error message appears only inside it. If the Chinese speech still needs more time, keep the visual information and allow a modest tempo change or brief hold instead.

Render from source frames once:

```bash
python3 scripts/render_cut_video.py source.mp4 cut_plan.json edited_video.mp4 --fps 60
```

### 6. Build the shared timeline

Place every Chinese track on the edited visual timeline. Respect chapter/scene boundaries, keep pauses short and intentional, and keep subtitle cues inside the corresponding spoken audio. Use [schemas.md](references/schemas.md) for schedule fields.

Mux the edited video, mastered Chinese audio, and Chinese subtitle stream. Make Chinese audio and subtitles default while also exporting the `.srt`. Use AAC 48 kHz stereo for the delivery copy unless the user requests another format.

### 7. Validate before calling it final

Run:

```bash
python3 scripts/validate_final.py final.mp4 final.srt --expected-fps 60
```

Then apply every gate in [quality-gates.md](references/quality-gates.md). Visually inspect at least the opening, closing, every chapter boundary, several fast/slow delivery sections, and every semantic cut. Listen with headphones for abrupt tempo changes, clipped consonants, long dead air, duplicated words, and subtitle drift.

Write machine-readable pacing, timeline, cut, and validation reports plus a short Chinese acceptance note.

### 8. Write the Obsidian companion article

Read [obsidian-article.md](references/obsidian-article.md). Locate the correct vault and subject folder rather than inventing a new root. Write an Obsidian-flavored Markdown article suitable for later publication to 微信公众号. The article must stand on its own and must not merely reproduce the transcript.

When requested, generate a 2.35:1 cover and a small set of purposeful inline illustrations. Store article assets beside the note or in the vault's established attachment folder and use relative Obsidian embeds.

### 9. Deliver and clean up

Present the final video, external SRT, reports, Obsidian note, and image assets. After the user approves the final version, build an explicit keep/delete manifest. Keep the source, final master, SRT, final reports, note, and referenced assets. Remove old renders, abandoned samples, and rebuildable uncompressed intermediates. Never delete shared models, dependencies, source media, or files referenced by the final article.

## Recovery rules

- If a download fails, preserve the partial diagnostics and retry with the media downloader or `yt-dlp`; do not use a screen recording as the first fallback.
- If local voice cloning is unavailable, stop before spending money. Offer neutral local TTS or request direction.
- If Chinese speech cannot fit without distortion, revise the translation or cut redundant visuals; do not exceed comfortable tempo merely to match lips.
- If screen-state analysis is uncertain, keep the footage. A slightly longer video is preferable to missing information.
- If the Obsidian vault cannot be identified safely, produce the article in the project output and ask where it should be moved.
