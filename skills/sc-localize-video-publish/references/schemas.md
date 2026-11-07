# Interchange schemas

These are minimum fields; additional audit fields are welcome.

## Bilingual segments

```json
[
  {
    "id": 1,
    "start": 12.34,
    "end": 16.78,
    "en": "Original sentence.",
    "zh": "自然、准确的中文。"
  }
]
```

IDs must be stable and sequential. Times are source seconds.

## Dubbing tracks

```json
[
  {
    "id": 1,
    "source_ids": [1, 2],
    "start": 12.34,
    "end": 21.1,
    "duration": 8.76,
    "zh": "一个可自然朗读的完整语义组。"
  }
]
```

Track IDs must match `group_001.wav`, `group_002.wav`, and so on.

## Tempo plan and duration report

```json
{
  "method": {
    "tempo_range": [0.92, 1.08],
    "maximum_adjacent_step": 0.06
  },
  "tracks": [
    {
      "id": 1,
      "source_ids": [1, 2],
      "tempo_factor": 1.035,
      "pause_after": 0.14,
      "style": "略快",
      "rendered_duration": 6.42
    }
  ]
}
```

`tempo_factor > 1` means faster playback through FFmpeg `atempo`.

## Cut plan

```json
{
  "source_duration": 910.5,
  "output_duration": 729.7,
  "output_fps": 60,
  "chapters": [
    {
      "id": 1,
      "tracks": [1, 5],
      "source_start": 0.0,
      "source_end": 65.0
    }
  ],
  "cuts": [
    {
      "start": 18.0,
      "end": 22.0,
      "duration": 4.0,
      "method": "semantic_review",
      "rationale": "纯人物镜头；无屏幕信息"
    }
  ]
}
```

Cuts use source time, are sorted, do not overlap, and are quantized to the intended output frame rate. Recompute output duration from cuts instead of trusting a hand-entered value.

## Final audio/subtitle schedule

```json
{
  "sample_rate": 48000,
  "final_duration": 729.7,
  "tracks": [
    {
      "id": 1,
      "audio_start": 0.8,
      "audio_end": 7.22,
      "tempo_factor": 1.035,
      "pause_after": 0.14,
      "source_ids": [1, 2]
    }
  ],
  "cues": [
    {"id": 1, "track_id": 1, "start": 0.8, "end": 4.1, "text": "……"}
  ]
}
```

All audio and cue times use the edited output timeline.
