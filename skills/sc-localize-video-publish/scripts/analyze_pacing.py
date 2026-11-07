#!/usr/bin/env python3
"""Derive modest Chinese tempo changes from original English delivery."""

from __future__ import annotations

import argparse
import json
import re
import wave
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path, help="mono PCM16 original speech WAV")
    parser.add_argument("tracks", type=Path, help="dubbing track JSON")
    parser.add_argument("segments", type=Path, help="bilingual segment JSON")
    parser.add_argument("output", type=Path)
    parser.add_argument("--silence-db", type=float, default=-38.0)
    parser.add_argument("--hop", type=float, default=0.01)
    parser.add_argument("--tempo-min", type=float, default=0.92)
    parser.add_argument("--tempo-max", type=float, default=1.08)
    parser.add_argument("--max-step", type=float, default=0.06)
    parser.add_argument("--density-weight", type=float, default=0.85)
    return parser.parse_args()


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*", text))


def robust_unit(values: np.ndarray) -> np.ndarray:
    median = float(np.median(values))
    q10, q90 = np.quantile(values, [0.1, 0.9])
    half_span = max(float(q90 - q10) / 2.0, 1e-6)
    return np.clip((values - median) / half_span, -1.0, 1.0)


def boundary_silence(silent: np.ndarray, boundary: int, hop: float) -> float:
    radius = round(0.35 / hop)
    center_radius = round(0.12 / hop)
    start = max(0, boundary - radius)
    end = min(len(silent), boundary + radius + 1)
    local = silent[start:end]
    best = 0
    run_start: int | None = None
    for index, value in enumerate(np.r_[local, False]):
        if value and run_start is None:
            run_start = index
        elif not value and run_start is not None:
            absolute_start = start + run_start
            absolute_end = start + index
            if absolute_start <= boundary + center_radius and absolute_end >= boundary - center_radius:
                best = max(best, absolute_end - absolute_start)
            run_start = None
    return best * hop


def pace_label(factor: float) -> str:
    if factor <= 0.94:
        return "舒缓"
    if factor < 0.98:
        return "略慢"
    if factor <= 1.02:
        return "自然"
    if factor < 1.06:
        return "略快"
    return "强调加快"


def main() -> None:
    args = parse_args()
    if not 0.5 <= args.density_weight <= 1.0:
        raise ValueError("--density-weight must be between 0.5 and 1.0")
    tracks = json.loads(args.tracks.read_text(encoding="utf-8"))
    segments = {int(item["id"]): item for item in json.loads(args.segments.read_text(encoding="utf-8"))}
    with wave.open(str(args.audio), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise ValueError("expected mono PCM16 reference audio")
        sample_rate = wav.getframerate()
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32)

    hop_samples = round(args.hop * sample_rate)
    frame_count = len(samples) // hop_samples
    framed = samples[: frame_count * hop_samples].reshape(frame_count, hop_samples)
    rms = np.sqrt(np.mean(framed * framed, axis=1) + 1.0)
    db = 20.0 * np.log10(rms / 32768.0)
    silent = db <= args.silence_db

    rows: list[dict] = []
    for track in tracks:
        start = float(track["start"])
        end = float(track["end"])
        start_index = max(0, round(start / args.hop))
        end_index = min(len(db), round(end / args.hop))
        track_db = db[start_index:end_index]
        if not len(track_db):
            raise ValueError(f"track {track['id']} is outside reference audio")
        active = track_db > args.silence_db
        english = " ".join(segments[int(source_id)]["en"] for source_id in track["source_ids"])
        words = word_count(english)
        duration = max(end - start, 0.001)
        active_seconds = max(float(active.sum()) * args.hop, 0.2)
        active_values = track_db[active]
        rows.append({
            "id": int(track["id"]),
            "source_ids": track["source_ids"],
            "word_count": words,
            "delivery_words_per_second": words / duration,
            "articulation_words_per_second": words / active_seconds,
            "active_ratio": float(active.mean()),
            "active_p75_db": float(np.percentile(active_values, 75)) if len(active_values) else -100.0,
            "boundary_silence": boundary_silence(silent, end_index, args.hop),
            "zh": track["zh"],
        })

    delivery = np.array([item["delivery_words_per_second"] for item in rows])
    energy = np.array([item["active_p75_db"] for item in rows])
    energy_weight = 1.0 - args.density_weight
    scores = args.density_weight * robust_unit(delivery) + energy_weight * robust_unit(energy)
    amplitude = min(0.085, (args.tempo_max - args.tempo_min) / 2.0)
    factors = np.clip(1.0 + amplitude * scores, args.tempo_min, args.tempo_max)

    for _ in range(2):
        for index in range(1, len(factors)):
            factors[index] = np.clip(factors[index], factors[index - 1] - args.max_step, factors[index - 1] + args.max_step)
        for index in range(len(factors) - 2, -1, -1):
            factors[index] = np.clip(factors[index], factors[index + 1] - args.max_step, factors[index + 1] + args.max_step)
    factors = np.round(factors / 0.005) * 0.005

    for item, score, factor in zip(rows, scores, factors):
        pause = float(np.clip(0.08 + 0.65 * min(float(item["boundary_silence"]), 0.32), 0.08, 0.28))
        item["pace_score"] = round(float(score), 4)
        item["tempo_factor"] = round(float(factor), 3)
        item["pause_after"] = round(pause / 0.01) * 0.01
        item["style"] = pace_label(float(factor))
        for key in ("delivery_words_per_second", "articulation_words_per_second", "active_ratio", "active_p75_db", "boundary_silence"):
            item[key] = round(float(item[key]), 4)

    document = {
        "method": {
            "description": f"{args.density_weight:.0%} original delivery density + {energy_weight:.0%} active-speech energy",
            "tempo_range": [args.tempo_min, args.tempo_max],
            "maximum_adjacent_step": args.max_step,
            "silence_threshold_db": args.silence_db,
            "pause_range": [0.08, 0.28],
        },
        "tracks": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "tracks": len(rows),
        "tempo_min": min(item["tempo_factor"] for item in rows),
        "tempo_max": max(item["tempo_factor"] for item in rows),
        "pause_min": min(item["pause_after"] for item in rows),
        "pause_max": max(item["pause_after"] for item in rows),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
