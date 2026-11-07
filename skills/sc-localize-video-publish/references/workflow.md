# Workflow and approval gates

## Project layout

Use a stable structure:

```text
project/
  source/               original download and provenance
  work/
    transcript/
    translation/
    voice/
    pacing/
    visual-analysis/
    edit/
  outputs/              current approved candidates only
  reports/              machine-readable QA and acceptance notes
```

Use versioned work folders, but human-readable final filenames. Never overwrite the source.

## Gate A: source integrity

Before transcription, save `ffprobe` JSON and confirm:

- source duration, width, height, and real frame rate;
- whether variable frame rate is present;
- audio sample rate/channels;
- available captions and languages;
- source URL and download timestamp.

## Gate B: translation and voice sample

Unless the user already approved the exact voice/translation setup, render a 60–90 second sample. Prefer a passage with clear, continuous speech and some screen activity. Review:

- terminology and meaning;
- speaker resemblance and pronunciation;
- natural Chinese phrasing;
- subtitle segmentation and safe margins;
- absence of long artificial silence.

Lip-sync is a separate optional scope and is off by default.

## Gate C: pacing plan

For each dubbing track, record natural duration, rendered duration, tempo factor, pause after, and style label. Use original delivery density and energy as guidance. Recommended starting constraints:

- tempo: 0.92–1.08;
- adjacent factor delta: at most 0.06;
- ordinary inter-track pause: 0.08–0.28 seconds;
- longer pauses only at genuine scene/chapter boundaries.

Listen to transitions. Numerical compliance does not prove naturalness.

## Gate D: visual cut plan

Construct cuts in source time and quantize them to the output frame rate. Protect:

- transcript and chapter boundaries;
- typing, scrolling, clicks, loading completion, and result states;
- unique code, commands, errors, diagrams, and release/version information;
- pointer movement when it carries explanatory meaning.

For every semantic cut, capture at least one frame before, one inside, and one after. The rationale must state what is removed and where the retained information remains visible.

## Gate E: shared timeline

Map source time to edited time once. Use the same mapping for audio placement, subtitle cues, reports, and article timestamps. Do not retime subtitles independently by eye after muxing.

## Gate F: final QA

Validate streams and timing mechanically, then watch and listen. Do not approve solely from `ffprobe`. Check cuts, tempo transitions, subtitle boundaries, frame cadence, and the full final duration.

## Retention after approval

Create two explicit lists before deletion.

Keep:

- original source and provenance;
- approved final master;
- external SRT;
- final translation/track/cut/timing reports needed to revise the work;
- Obsidian article and every referenced image;
- reusable local models and dependencies.

Delete when approved:

- superseded final renders and subtitles;
- abandoned lip-sync samples;
- duplicate cut-only renders already muxed into the final;
- rebuildable timeline WAV files and temporary extracted audio;
- contact sheets and caches no longer referenced by reports or articles.

Measure disk usage before and after. Never use broad wildcards that could match the approved final.
