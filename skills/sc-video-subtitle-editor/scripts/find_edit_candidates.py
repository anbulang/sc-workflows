#!/usr/bin/env python3
"""Find reviewable edit candidates in whisper.cpp full JSON output.

The script detects long silence, conservative language-specific standalone
fillers, and adjacent repeated tokens. It never approves edits: every result
must be interpreted against the video's content profile and reviewed by the
user before it enters an EDL.

Usage:
  python3 find_edit_candidates.py transcript.json candidates.json \
    [--duration-seconds N] [--language auto|zh|en|...] \
    [--silence-ms N] [--filler WORD ...]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


INTERNAL_TOKEN = re.compile(r"^\[_.*\]$")
STRIP_PUNCT = "，。？！,.?!、；;：:‘’“”\"'()（）[]【】"
DEFAULT_SILENCE_MS = 2500

# Keep these lists deliberately conservative. Discourse markers such as
# English "like" or "you know" can carry meaning and are not included.
FILLERS_BY_LANGUAGE = {
    "zh": {"嗯", "啊", "呃", "额", "诶", "唉", "呐", "呗"},
    "en": {"um", "uh", "erm", "hmm", "hm"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript_json", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument(
        "--duration-seconds",
        type=float,
        help="Total media duration; enables trailing-silence detection.",
    )
    parser.add_argument(
        "--language",
        default="auto",
        help="BCP-47/Whisper language code. Unknown languages get no built-in filler list.",
    )
    parser.add_argument(
        "--silence-ms", type=int, default=DEFAULT_SILENCE_MS, help="Long-silence threshold."
    )
    parser.add_argument(
        "--filler",
        action="append",
        default=[],
        help="Additional standalone filler approved for detection; repeat as needed.",
    )
    return parser.parse_args()


def normalize_language(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    code = value.strip().lower().replace("_", "-").split("-", 1)[0]
    aliases = {"chinese": "zh", "english": "en"}
    return aliases.get(code, code)


def metadata_language(data: dict[str, Any]) -> str | None:
    direct = normalize_language(data.get("language"))
    if direct:
        return direct
    result = data.get("result")
    if isinstance(result, dict):
        return normalize_language(result.get("language"))
    return None


def load_tokens(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)

    transcription = data.get("transcription")
    if not isinstance(transcription, list):
        raise ValueError("transcript JSON has no 'transcription' list; use whisper-cli -oj -ojf")

    tokens: list[dict[str, Any]] = []
    for segment in transcription:
        for token in segment.get("tokens", []):
            text = str(token.get("text", "")).strip()
            if not text or INTERNAL_TOKEN.match(text):
                continue
            offsets = token.get("offsets", {})
            if "from" not in offsets or "to" not in offsets:
                continue
            tokens.append({"text": text, "from": int(offsets["from"]), "to": int(offsets["to"])})
    return tokens, metadata_language(data)


def infer_language(tokens: list[dict[str, Any]]) -> str | None:
    text = "".join(token["text"] for token in tokens[:500])
    if not text:
        return None
    cjk = len(re.findall(r"[\u3400-\u9fff]", text))
    visible = len(re.findall(r"\w", text, flags=re.UNICODE))
    return "zh" if visible and cjk / visible >= 0.2 else None


def comparable_text(text: str) -> str:
    return text.strip(STRIP_PUNCT).casefold()


def find_candidates(
    tokens: list[dict[str, Any]],
    fillers: set[str],
    silence_ms: int,
    duration_ms: int | None = None,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    if tokens and tokens[0]["from"] > silence_ms:
        candidates.append(
            {
                "type": "long_silence",
                "text": f"[leading silence {tokens[0]['from'] / 1000:.1f}s]",
                "from": 0,
                "to": tokens[0]["from"],
            }
        )

    normalized_fillers = {comparable_text(word) for word in fillers if comparable_text(word)}
    for token in tokens:
        if comparable_text(token["text"]) in normalized_fillers:
            candidates.append(
                {
                    "type": "filler_word",
                    "text": token["text"],
                    "from": token["from"],
                    "to": token["to"],
                }
            )

    i = 0
    while i < len(tokens) - 1:
        first = tokens[i]
        first_text = comparable_text(first["text"])
        second = tokens[i + 1]
        if (
            first_text
            and first_text == comparable_text(second["text"])
            and len(first_text) <= 8
            and second["from"] - first["to"] < 400
        ):
            j = i + 1
            while j + 1 < len(tokens):
                following = tokens[j + 1]
                if (
                    comparable_text(following["text"]) != first_text
                    or following["from"] - tokens[j]["to"] >= 400
                ):
                    break
                j += 1
            candidates.append(
                {
                    "type": "repeat_candidate",
                    "text": "".join(tokens[k]["text"] for k in range(i, j + 1)),
                    "from": tokens[i]["from"],
                    "to": tokens[j]["to"],
                }
            )
            i = j + 1
            continue
        i += 1

    for left, right in zip(tokens, tokens[1:]):
        gap = right["from"] - left["to"]
        if gap > silence_ms:
            candidates.append(
                {
                    "type": "long_silence",
                    "text": f"[silence {gap / 1000:.1f}s]",
                    "from": left["to"],
                    "to": right["from"],
                }
            )

    if tokens and duration_ms is not None:
        trailing = duration_ms - tokens[-1]["to"]
        if trailing > silence_ms:
            candidates.append(
                {
                    "type": "long_silence",
                    "text": f"[trailing silence {trailing / 1000:.1f}s]",
                    "from": tokens[-1]["to"],
                    "to": duration_ms,
                }
            )

    candidates.sort(key=lambda candidate: (candidate["from"], candidate["to"], candidate["type"]))
    return candidates


def main() -> None:
    args = parse_args()
    if args.silence_ms <= 0:
        raise SystemExit("--silence-ms must be positive")

    tokens, detected = load_tokens(args.transcript_json)
    requested = normalize_language(args.language)
    language = (detected or infer_language(tokens)) if requested in {None, "auto"} else requested
    fillers = set(FILLERS_BY_LANGUAGE.get(language or "", set()))
    fillers.update(args.filler)
    duration_ms = int(round(args.duration_seconds * 1000)) if args.duration_seconds is not None else None
    candidates = find_candidates(tokens, fillers, args.silence_ms, duration_ms)

    by_type: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        by_type.setdefault(candidate["type"], []).append(candidate)

    print(f"language: {language or 'unknown'}; filler lexicon: {len(fillers)}")
    print(f"total candidates: {len(candidates)}")
    notes = {
        "long_silence": "review against video context",
        "filler_word": "review in surrounding speech",
        "repeat_candidate": "HIGH RISK; never auto-cut",
    }
    for candidate_type, items in by_type.items():
        duration = sum(item["to"] - item["from"] for item in items) / 1000
        print(f"  {candidate_type}: {len(items)} instances, {duration:.1f}s -- {notes[candidate_type]}")

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    with args.output_json.open("w", encoding="utf-8") as handle:
        json.dump(candidates, handle, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
