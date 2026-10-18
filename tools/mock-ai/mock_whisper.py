#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import wave
from pathlib import Path
from typing import Any

from mock_state import WHISPER_AI, find_state_dir, record_call, take_scenario_rule

MS_PER_SECOND = 1000
SECONDS_PER_MINUTE = 60
DEFAULT_LINE_EVERY_SEC = 10
LINE_LENGTH_SEC = 4
FLAGS_WITH_VALUE = frozenset({"-m", "-f", "-l", "-of", "-t", "-p"})


def parse_flags(args: list[str]) -> dict[str, str]:
    flags: dict[str, str] = {}
    index = 0
    while index < len(args):
        if args[index] in FLAGS_WITH_VALUE and index + 1 < len(args):
            flags[args[index]] = args[index + 1]
            index += 2
            continue
        flags[args[index]] = ""
        index += 1
    return flags


def read_duration_ms(audio_path: Path) -> int:
    with wave.open(str(audio_path), "rb") as audio:
        return audio.getnframes() * MS_PER_SECOND // audio.getframerate()


def build_default_segments(duration_ms: int) -> list[list[Any]]:
    segments = []
    for start_sec in range(0, max(1, duration_ms // MS_PER_SECOND), DEFAULT_LINE_EVERY_SEC):
        end_sec = min(start_sec + LINE_LENGTH_SEC, duration_ms / MS_PER_SECOND)
        minutes, seconds = divmod(start_sec, SECONDS_PER_MINUTE)
        segments.append([start_sec, end_sec, f" Mock line at {minutes:02d}:{seconds:02d}."])
    return segments


def to_whisper_json(segments: list[list[Any]], language: str) -> dict[str, Any]:
    return {
        "result": {"language": language},
        "transcription": [
            {
                "offsets": {"from": int(start * MS_PER_SECOND), "to": int(end * MS_PER_SECOND)},
                "text": text,
            }
            for start, end, text in segments
        ],
    }


def main(args: list[str]) -> int:
    flags = parse_flags(args)
    audio_path = Path(flags["-f"])
    language = flags.get("-l", "auto")
    detected_language = "en" if language == "auto" else language
    state_dir = find_state_dir()
    rule = take_scenario_rule(state_dir, WHISPER_AI, audio_path.name) or {}
    if rule.get("exit"):
        sys.stderr.write(str(rule.get("stderr", "mock whisper failed")) + "\n")
        return int(rule["exit"])
    duration_ms = read_duration_ms(audio_path)
    segments = rule.get("segments")
    if segments is None:
        segments = build_default_segments(duration_ms)
    output_path = Path(flags["-of"]).with_suffix(".json")
    output_path.write_text(
        json.dumps(to_whisper_json(segments, detected_language)), encoding="utf-8"
    )
    record_call(
        state_dir,
        {
            "ai": WHISPER_AI,
            "model": flags.get("-m"),
            "language": language,
            "durationMs": duration_ms,
            "segments": len(segments),
            "scenario": rule or None,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
