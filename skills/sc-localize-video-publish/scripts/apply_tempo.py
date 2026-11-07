#!/usr/bin/env python3
"""Apply a pitch-preserving FFmpeg tempo plan to sentence/group WAV files."""

from __future__ import annotations

import argparse
import json
import subprocess
import wave
from pathlib import Path


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / wav.getframerate()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tempo_plan", type=Path)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--pattern", default="group_{id:03d}.wav")
    parser.add_argument("--sample-rate", type=int, default=48000)
    args = parser.parse_args()

    plan = json.loads(args.tempo_plan.read_text(encoding="utf-8"))["tracks"]
    if not plan:
        raise ValueError("tempo plan has no tracks")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report: list[dict] = []
    for index, item in enumerate(plan, start=1):
        track_id = int(item["id"])
        filename = args.pattern.format(id=track_id)
        source = args.input_dir / filename
        output = args.output_dir / filename
        if not source.is_file():
            raise FileNotFoundError(source)
        factor = float(item["tempo_factor"])
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
            "-af", f"atempo={factor:.6f},afade=t=in:st=0:d=0.012,areverse,afade=t=in:st=0:d=0.025,areverse",
            "-ar", str(args.sample_rate), "-ac", "1", "-c:a", "pcm_s16le", str(output),
        ], check=True)
        natural_duration = wav_duration(source)
        rendered_duration = wav_duration(output)
        report.append({
            **item,
            "natural_duration": round(natural_duration, 6),
            "rendered_duration": round(rendered_duration, 6),
            "actual_tempo_factor": round(natural_duration / rendered_duration, 4),
        })
        print(f"[{index:03}/{len(plan):03}] {item.get('style', '自然')}: {natural_duration:.3f}s -> {rendered_duration:.3f}s ({factor:.3f}x)", flush=True)

    document = {
        "tracks": report,
        "summary": {
            "count": len(report),
            "natural_duration": round(sum(item["natural_duration"] for item in report), 6),
            "rendered_duration": round(sum(item["rendered_duration"] for item in report), 6),
            "tempo_min": min(item["tempo_factor"] for item in report),
            "tempo_max": max(item["tempo_factor"] for item in report),
            "actual_tempo_min": min(item["actual_tempo_factor"] for item in report),
            "actual_tempo_max": max(item["actual_tempo_factor"] for item in report),
            "pause_total": round(sum(float(item.get("pause_after", 0.0)) for item in report), 4),
        },
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(document["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
