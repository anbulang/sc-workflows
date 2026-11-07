#!/usr/bin/env python3
"""Render a frame-quantized cut-only video from a JSON cut plan."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fps", type=float)
    parser.add_argument("--codec", default="libx264")
    parser.add_argument("--preset", default="fast")
    parser.add_argument("--crf", type=int, default=17)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    fps = float(args.fps or plan.get("output_fps", 60.0))
    cuts = sorted(plan.get("cuts", []), key=lambda item: float(item["start"]))
    for previous, current in zip(cuts, cuts[1:]):
        if float(current["start"]) < float(previous["end"]) - 1e-9:
            raise ValueError(f"overlapping cuts: {previous} / {current}")
    drop_ranges: list[str] = []
    for cut in cuts:
        start_frame = round(float(cut["start"]) * fps)
        end_frame = round(float(cut["end"]) * fps) - 1
        if end_frame >= start_frame:
            drop_ranges.append(f"between(n\\,{start_frame}\\,{end_frame})")
    if not drop_ranges:
        raise ValueError("cut plan is empty")
    fps_text = f"{fps:.12g}"
    video_filter = f"select='not({'+'.join(drop_ranges)})',setpts=N/({fps_text}*TB)"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-hide_banner", "-y", "-stats_period", "15", "-i", str(args.source), "-an",
        "-vf", video_filter, "-fps_mode", "cfr", "-r", fps_text,
        "-c:v", args.codec, "-preset", args.preset, "-crf", str(args.crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(args.output),
    ], check=True)


if __name__ == "__main__":
    main()
