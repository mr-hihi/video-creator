import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.modules.jobs.film_analysis.media_parts import MediaPart
from app.modules.jobs.video_to_markdown.markdown import Speaker, SpeakerVoices
from app.modules.jobs.video_to_markdown.moments import FRAME_END_MARGIN_MS, MIN_MOMENT_GAP_MS

MAX_SPEAKER_NAME_LENGTH = 100
MAX_VOICE_LENGTH = 500
MAX_SOUND_DESCRIPTION_LENGTH = 200


class SoundKind(StrEnum):
    ACTION = "action"
    SILENCE = "silence"
    AMBIENT = "ambient"
    MUSIC = "music"


SOUND_KIND_LABELS = {
    SoundKind.ACTION: "Action",
    SoundKind.SILENCE: "Silence",
    SoundKind.AMBIENT: "Ambient",
    SoundKind.MUSIC: "Music",
}
SPEAKERS_AND_SOUNDS_SCHEMA = {
    "type": "object",
    "properties": {
        "speakers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "voice": {"type": "string"}},
                "required": ["name", "voice"],
            },
        },
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"atMs": {"type": "integer"}, "speaker": {"type": "string"}},
                "required": ["atMs", "speaker"],
            },
        },
        "sounds": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "atMs": {"type": "integer"},
                    "kind": {"type": "string", "enum": [kind.value for kind in SoundKind]},
                    "description": {"type": "string"},
                },
                "required": ["atMs", "kind", "description"],
            },
        },
    },
    "required": ["speakers", "lines", "sounds"],
}


@dataclass(frozen=True)
class SpeakerLine:
    at_ms: int
    speaker: str


@dataclass(frozen=True)
class HeardSound:
    at_ms: int
    kind: SoundKind
    description: str


@dataclass(frozen=True)
class AudioNotes:
    speakers: list[Speaker]
    lines: list[SpeakerLine]
    sounds: list[HeardSound]


@dataclass(frozen=True)
class AudioPartReply:
    part: MediaPart
    segment_starts_ms: frozenset[int]
    reply: Mapping[str, Any]


def normalize_audio_replies(part_replies: Sequence[AudioPartReply], duration_ms: int) -> AudioNotes:
    speakers_by_key: dict[str, Speaker] = {}
    for part_reply in part_replies:
        for entry in to_entries(part_reply.reply, "speakers"):
            speaker = to_speaker(entry)
            if speaker is not None:
                speakers_by_key.setdefault(speaker.name.casefold(), speaker)
    lines = [
        line for part_reply in part_replies for line in to_part_lines(part_reply, speakers_by_key)
    ]
    return AudioNotes(
        speakers=list(speakers_by_key.values()),
        lines=lines,
        sounds=to_kept_sounds(part_replies, duration_ms),
    )


def to_part_lines(
    part_reply: AudioPartReply, speakers_by_key: dict[str, Speaker]
) -> list[SpeakerLine]:
    lines_by_start_ms: dict[int, SpeakerLine] = {}
    for entry in to_entries(part_reply.reply, "lines"):
        at_ms = to_whole_ms(entry.get("atMs"))
        name = to_trimmed_text(entry.get("speaker"), MAX_SPEAKER_NAME_LENGTH)
        if at_ms not in part_reply.segment_starts_ms or not name or at_ms in lines_by_start_ms:
            continue
        speaker = speakers_by_key.setdefault(name.casefold(), Speaker(name=name, voice=""))
        lines_by_start_ms[at_ms] = SpeakerLine(at_ms=at_ms, speaker=speaker.name)
    return list(lines_by_start_ms.values())


def to_kept_sounds(part_replies: Sequence[AudioPartReply], duration_ms: int) -> list[HeardSound]:
    last_capturable_ms = max(duration_ms - FRAME_END_MARGIN_MS, 0)
    candidates = sorted(
        (
            HeardSound(
                at_ms=min(max(sound.at_ms, 0), last_capturable_ms),
                kind=sound.kind,
                description=sound.description,
            )
            for part_reply in part_replies
            for sound in to_part_sounds(part_reply)
        ),
        key=lambda sound: sound.at_ms,
    )
    kept_sounds: list[HeardSound] = []
    for candidate in candidates:
        if kept_sounds and candidate.at_ms - kept_sounds[-1].at_ms < MIN_MOMENT_GAP_MS:
            continue
        kept_sounds.append(candidate)
    return kept_sounds


def to_part_sounds(part_reply: AudioPartReply) -> list[HeardSound]:
    part = part_reply.part
    sounds = []
    for entry in to_entries(part_reply.reply, "sounds"):
        at_ms = to_whole_ms(entry.get("atMs"))
        kind = entry.get("kind")
        description = to_trimmed_text(entry.get("description"), MAX_SOUND_DESCRIPTION_LENGTH)
        if at_ms is None or kind not in SOUND_KIND_LABELS or not description:
            continue
        sounds.append(
            HeardSound(
                at_ms=min(max(at_ms, part.start_ms), part.end_ms),
                kind=SoundKind(kind),
                description=description,
            )
        )
    return sounds


def to_speaker(entry: Mapping[str, Any]) -> Speaker | None:
    name = to_trimmed_text(entry.get("name"), MAX_SPEAKER_NAME_LENGTH)
    if not name:
        return None
    return Speaker(name=name, voice=to_trimmed_text(entry.get("voice"), MAX_VOICE_LENGTH))


def to_entries(reply: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    entries = reply.get(key)
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, Mapping)]


def to_trimmed_text(value: Any, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


def to_whole_ms(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return round(value)
    return None


def to_sound_title(sound: HeardSound) -> str:
    return f"{SOUND_KIND_LABELS[sound.kind]}: {sound.description}"


def to_speaker_voices(notes: AudioNotes) -> SpeakerVoices:
    return SpeakerVoices(
        speakers=notes.speakers,
        speaker_names_by_start_ms={line.at_ms: line.speaker for line in notes.lines},
    )


def to_speaker_lines(speakers: Sequence[Speaker]) -> list[str]:
    return [
        f"- {speaker.name} — {speaker.voice}" if speaker.voice else f"- {speaker.name}"
        for speaker in speakers
    ]


def audio_notes_to_json(notes: AudioNotes) -> dict[str, Any]:
    return {
        "speakers": [{"name": speaker.name, "voice": speaker.voice} for speaker in notes.speakers],
        "lines": [{"atMs": line.at_ms, "speaker": line.speaker} for line in notes.lines],
        "sounds": [
            {"atMs": sound.at_ms, "kind": sound.kind.value, "description": sound.description}
            for sound in notes.sounds
        ],
    }
