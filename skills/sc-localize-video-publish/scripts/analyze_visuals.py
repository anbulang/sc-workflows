#!/usr/bin/env python3
"""Measure screen changes while optionally excluding a speaker/PiP crop."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fps", type=float, default=5.0)
    parser.add_argument("--width", type=int, default=360)
    parser.add_argument("--height", type=int, default=270)
    parser.add_argument("--crop", help="FFmpeg crop value, for example 1440:1080:0:0")
    parser.add_argument("--grid-rows", type=int, default=15)
    parser.add_argument("--grid-cols", type=int, default=20)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.width % args.grid_cols or args.height % args.grid_rows:
        raise ValueError("analysis width/height must be divisible by the signature grid")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame_bytes = args.width * args.height
    filters = [f"fps={args.fps}"]
    if args.crop:
        filters.append(f"crop={args.crop}")
    filters.extend([f"scale={args.width}:{args.height}:flags=area", "format=gray"])
    process = subprocess.Popen([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(args.video), "-an",
        "-vf", ",".join(filters), "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1",
    ], stdout=subprocess.PIPE)
    assert process.stdout is not None

    block_height = args.height // args.grid_rows
    block_width = args.width // args.grid_cols
    metrics: list[dict[str, float | int]] = []
    signatures: list[np.ndarray] = []
    previous: np.ndarray | None = None
    index = 0
    while True:
        data = process.stdout.read(frame_bytes)
        if len(data) != frame_bytes:
            break
        frame = np.frombuffer(data, dtype=np.uint8).reshape(args.height, args.width)
        if previous is None:
            mean_diff = changed_fraction = block_max = 0.0
        else:
            diff = np.abs(frame.astype(np.int16) - previous.astype(np.int16))
            mean_diff = float(diff.mean())
            changed_fraction = float((diff >= 14).mean())
            blocks = diff.reshape(args.grid_rows, block_height, args.grid_cols, block_width).mean(axis=(1, 3))
            block_max = float(blocks.max())
        signature = frame.reshape(args.grid_rows, block_height, args.grid_cols, block_width).mean(axis=(1, 3)).astype(np.uint8)
        metrics.append({
            "index": index,
            "time": round(index / args.fps, 3),
            "mean_diff": round(mean_diff, 5),
            "changed_fraction": round(changed_fraction, 6),
            "block_max": round(block_max, 5),
        })
        signatures.append(signature)
        previous = frame.copy()
        index += 1

    return_code = process.wait()
    if return_code != 0:
        raise SystemExit(return_code)
    if not signatures:
        raise ValueError("no video frames decoded")
    args.output.write_text(json.dumps({
        "fps": args.fps,
        "width": args.width,
        "height": args.height,
        "crop": args.crop,
        "grid": [args.grid_rows, args.grid_cols],
        "frames": metrics,
    }, ensure_ascii=False), encoding="utf-8")
    np.savez_compressed(args.output.with_suffix(".npz"), signatures=np.stack(signatures), fps=np.array([args.fps], dtype=np.float32))
    print(f"wrote {len(metrics)} samples to {args.output}")


if __name__ == "__main__":
    main()
