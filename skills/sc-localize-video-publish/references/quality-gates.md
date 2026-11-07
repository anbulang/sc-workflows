# Final quality gates

## Mechanical

- Video duration, audio duration, and last subtitle end agree within 100 ms unless the ending intentionally contains silence.
- Frame count agrees with `duration × fps` within one frame.
- Output resolution and frame rate match the intended delivery specification.
- Chinese audio is present, 48 kHz, and marked default.
- Chinese subtitle stream is present and marked default; external SRT decodes as UTF-8.
- Subtitle cues are ordered, positive in duration, non-overlapping, and inside the media duration.
- No cut ranges overlap or extend beyond source duration.
- Output duration equals source duration minus cut duration within one frame.
- Audio peak does not exceed -1 dBFS; target integrated loudness is normally about -17 LUFS for speech.

## Speech and pacing

- Translation is complete and does not invent facts.
- Names, versions, commands, and code identifiers are pronounced and written correctly.
- Tempo changes follow the original's emphasis and do not sound like an effect.
- No adjacent sentence sounds like a sudden gear change.
- No long silence was inserted merely to fill a visual gap.
- Pauses feel intentional; chapter pauses may be longer than sentence pauses.
- Track edges contain no clipped phonemes, clicks, or duplicated words.

## Picture

- Screen text and code remain as sharp as the single final encode allows.
- No unique UI state, command, error, result, diagram step, or version information was cut.
- Jump cuts in talking-head sections are acceptable but not distracting.
- Every semantic cut has been reviewed with adjacent frames and has a rationale.
- 60 fps sources remain 60 fps, with no unintentional 25/30 fps conversion.

## Subtitles

- Cues begin and end with their spoken phrases.
- Lines are short enough to read and avoid covering essential UI.
- Punctuation and terminology match the spoken Chinese.
- No cue remains on screen after its phrase has ended merely to fill time.

## Publication package

- Final filenames clearly identify the approved version.
- The acceptance note states duration, resolution, frame rate, audio/subtitle streams, pacing range, cuts, and known limitations.
- The Obsidian article links the source, accurately summarizes the video, and uses only existing asset paths.
- Obsolete renders are deleted only after the user approves the final.
