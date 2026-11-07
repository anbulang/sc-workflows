#!/usr/bin/env python3
"""Mux an edited video, Chinese master audio, and UTF-8 SRT without re-encoding video."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("audio", type=Path)
    parser.add_argument("srt", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--language", default="zho")
    parser.add_argument("--audio-title", default="中文配音")
    parser.add_argument("--subtitle-title", default="中文字幕")
    parser.add_argument("--audio-bitrate", default="192k")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-hide_banner", "-y", "-i", str(args.video), "-i", str(args.audio), "-i", str(args.srt),
        "-map", "0:v:0", "-map", "1:a:0", "-map", "2:0", "-c:v", "copy",
        "-c:a", "aac", "-b:a", args.audio_bitrate, "-ar", "48000", "-ac", "2", "-c:s", "mov_text",
        "-metadata:s:a:0", f"language={args.language}", "-metadata:s:a:0", f"title={args.audio_title}",
        "-metadata:s:s:0", f"language={args.language}", "-metadata:s:s:0", f"title={args.subtitle_title}",
        "-disposition:a:0", "default", "-disposition:s:0", "default", "-movflags", "+faststart", str(args.output),
    ], check=True)


if __name__ == "__main__":
    main()
