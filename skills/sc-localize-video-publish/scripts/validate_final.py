#!/usr/bin/env python3
"""Validate final media streams, cadence, duration, and an external SRT."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


TIME_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")


def seconds(value: str) -> float:
    match = TIME_RE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"invalid SRT time: {value}")
    hours, minutes, secs, millis = map(int, match.groups())
    return hours * 3600 + minutes * 60 + secs + millis / 1000


def rational(value: str) -> float:
    numerator, denominator = value.split("/", 1)
    return float(numerator) / float(denominator)


def parse_srt(path: Path) -> list[dict]:
    cues: list[dict] = []
    blocks = re.split(r"\n\s*\n", path.read_text(encoding="utf-8-sig").strip())
    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 3 or "-->" not in lines[1]:
            raise ValueError(f"invalid SRT block: {block[:80]!r}")
        start_text, end_text = lines[1].split("-->", 1)
        cues.append({"id": lines[0].strip(), "start": seconds(start_text), "end": seconds(end_text), "text": " ".join(lines[2:]).strip()})
    return cues


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("srt", type=Path)
    parser.add_argument("--expected-fps", type=float)
    parser.add_argument("--expected-width", type=int)
    parser.add_argument("--expected-height", type=int)
    parser.add_argument("--tolerance", type=float, default=0.1)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(args.video)
    ], text=True))
    streams = probe["streams"]
    video_streams = [stream for stream in streams if stream["codec_type"] == "video"]
    audio_streams = [stream for stream in streams if stream["codec_type"] == "audio"]
    subtitle_streams = [stream for stream in streams if stream["codec_type"] == "subtitle"]
    errors: list[str] = []
    if len(video_streams) != 1:
        errors.append(f"expected one video stream, found {len(video_streams)}")
    if not audio_streams:
        errors.append("no audio stream")
    if not subtitle_streams:
        errors.append("no embedded subtitle stream")
    duration = float(probe["format"]["duration"])
    fps = rational(video_streams[0].get("avg_frame_rate", "0/1")) if video_streams else 0.0
    width = int(video_streams[0].get("width", 0)) if video_streams else 0
    height = int(video_streams[0].get("height", 0)) if video_streams else 0
    if args.expected_fps is not None and abs(fps - args.expected_fps) > 0.01:
        errors.append(f"fps {fps:.6f} != expected {args.expected_fps:.6f}")
    if args.expected_width is not None and width != args.expected_width:
        errors.append(f"width {width} != expected {args.expected_width}")
    if args.expected_height is not None and height != args.expected_height:
        errors.append(f"height {height} != expected {args.expected_height}")
    if audio_streams and int(audio_streams[0].get("sample_rate", 0)) != 48000:
        errors.append(f"audio sample rate is {audio_streams[0].get('sample_rate')}, expected 48000")
    if audio_streams and int(audio_streams[0].get("disposition", {}).get("default", 0)) != 1:
        errors.append("first audio stream is not default")
    if subtitle_streams and int(subtitle_streams[0].get("disposition", {}).get("default", 0)) != 1:
        errors.append("first subtitle stream is not default")

    try:
        cues = parse_srt(args.srt)
    except (UnicodeDecodeError, ValueError) as exc:
        errors.append(str(exc))
        cues = []
    for previous, current in zip(cues, cues[1:]):
        if previous["end"] <= previous["start"]:
            errors.append(f"cue {previous['id']} has non-positive duration")
        if current["start"] < previous["end"] - 0.001:
            errors.append(f"cues {previous['id']} and {current['id']} overlap")
    if cues:
        if cues[-1]["end"] <= cues[-1]["start"]:
            errors.append(f"cue {cues[-1]['id']} has non-positive duration")
        if cues[-1]["end"] > duration + args.tolerance:
            errors.append(f"last cue ends at {cues[-1]['end']:.3f}s after media duration {duration:.3f}s")

    nb_frames = None
    if video_streams and video_streams[0].get("nb_frames", "N/A") not in (None, "N/A"):
        nb_frames = int(video_streams[0]["nb_frames"])
        expected_frames = round(duration * fps)
        if abs(nb_frames - expected_frames) > 1:
            errors.append(f"frame count {nb_frames} differs from duration×fps {expected_frames}")

    report = {
        "ok": not errors,
        "video": str(args.video),
        "srt": str(args.srt),
        "duration": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "frames": nb_frames,
        "audio_streams": len(audio_streams),
        "subtitle_streams": len(subtitle_streams),
        "srt_cues": len(cues),
        "last_cue_end": cues[-1]["end"] if cues else None,
        "errors": errors,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
