import re
from dataclasses import dataclass
from typing import Any

NON_SPEECH_MARKER = re.compile(r"^\s*[\[(].*[\])]\s*$")
MS_PER_SECOND = 1000
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600


@dataclass(frozen=True)
class TranscriptSegment:
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class Transcript:
    language: str
    segments: list[TranscriptSegment]


def whisper_json_to_transcript(whisper_json: dict[str, Any], requested_language: str) -> Transcript:
    detected_language = whisper_json.get("result", {}).get("language", requested_language)
    segments = [
        TranscriptSegment(
            start_ms=entry["offsets"]["from"], end_ms=entry["offsets"]["to"], text=entry["text"]
        )
        for entry in whisper_json.get("transcription", [])
        if is_speech(entry.get("text", ""))
    ]
    return Transcript(language=detected_language, segments=segments)


def is_speech(text: str) -> bool:
    return bool(text.strip()) and not NON_SPEECH_MARKER.match(text)


@dataclass(frozen=True)
class ClockTime:
    hours: int
    minutes: int
    seconds: int


def to_clock_time(position_ms: int) -> ClockTime:
    total_seconds = position_ms // MS_PER_SECOND
    hours, remainder = divmod(total_seconds, SECONDS_PER_HOUR)
    minutes, seconds = divmod(remainder, SECONDS_PER_MINUTE)
    return ClockTime(hours=hours, minutes=minutes, seconds=seconds)


def format_timestamp(position_ms: int) -> str:
    clock = to_clock_time(position_ms)
    if clock.hours:
        return f"{clock.hours}:{clock.minutes:02d}:{clock.seconds:02d}"
    return f"{clock.minutes:02d}:{clock.seconds:02d}"


def join_segment_texts(segments: list[TranscriptSegment]) -> str:
    return "".join(segment.text for segment in segments).strip()
