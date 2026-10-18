from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.modules.jobs.video_to_markdown.transcript import (
    Transcript,
    TranscriptSegment,
    is_speech,
)
from app.modules.jobs.youtube_to_markdown.video_info import VideoInfo

AUTO_LANGUAGE = "auto"
ORIGINAL_AUTO_TRACK_SUFFIX = "-orig"
LANGUAGE_SUBTAG_SEPARATOR = "-"
LINE_SEPARATOR = " "


class CaptionKind(StrEnum):
    MANUAL = "manual"
    AUTO = "auto"


@dataclass(frozen=True)
class CaptionTrack:
    code: str
    kind: CaptionKind

    @property
    def language(self) -> str:
        return to_primary_language(self.code)


class NoCaptionsError(Exception):
    def __init__(self):
        super().__init__("This video has no transcript on YouTube")


class MissingCaptionLanguageError(Exception):
    pass


def select_caption_track(video: VideoInfo, language: str) -> CaptionTrack:
    spoken_language = find_spoken_language(video)
    usable_tracks = _list_usable_tracks(video, spoken_language)
    if not usable_tracks:
        raise NoCaptionsError()
    if language == AUTO_LANGUAGE and not spoken_language:
        return usable_tracks[0]
    wanted_language = spoken_language if language == AUTO_LANGUAGE else language
    matching_tracks = [track for track in usable_tracks if track.language == wanted_language]
    if matching_tracks:
        return matching_tracks[0]
    if language == AUTO_LANGUAGE:
        raise NoCaptionsError()
    raise MissingCaptionLanguageError(
        f"No '{language}' captions on YouTube for this video. "
        f"Available: {describe_tracks(usable_tracks)}"
    )


def find_spoken_language(video: VideoInfo) -> str:
    if video.metadata_language:
        return to_primary_language(video.metadata_language)
    original_codes = [
        code for code in video.auto_caption_codes if code.endswith(ORIGINAL_AUTO_TRACK_SUFFIX)
    ]
    return to_primary_language(original_codes[0]) if original_codes else ""


def describe_tracks(tracks: list[CaptionTrack]) -> str:
    descriptions = dict.fromkeys(f"{track.language} ({track.kind})" for track in tracks)
    return ", ".join(descriptions)


def to_primary_language(code: str) -> str:
    return code.split(LANGUAGE_SUBTAG_SEPARATOR)[0].lower()


def json3_to_transcript(captions_json: dict[str, Any], language: str) -> Transcript:
    segments: list[TranscriptSegment] = []
    previous_text = ""
    for event in captions_json.get("events", []):
        text = _event_text(event)
        if not is_speech(text) or text == previous_text:
            continue
        start_ms = int(event.get("tStartMs", 0))
        segments.append(
            TranscriptSegment(
                start_ms=start_ms,
                end_ms=start_ms + int(event.get("dDurationMs", 0)),
                text=f"{LINE_SEPARATOR}{text}",
            )
        )
        previous_text = text
    return Transcript(language=language, segments=segments)


def _list_usable_tracks(video: VideoInfo, spoken_language: str) -> list[CaptionTrack]:
    manual_tracks = [CaptionTrack(code, CaptionKind.MANUAL) for code in video.manual_caption_codes]
    auto_code = _find_original_auto_code(video, spoken_language)
    auto_tracks = [CaptionTrack(auto_code, CaptionKind.AUTO)] if auto_code else []
    return manual_tracks + auto_tracks


def _find_original_auto_code(video: VideoInfo, spoken_language: str) -> str:
    original_codes = [
        code
        for code in video.auto_caption_codes
        if code.endswith(ORIGINAL_AUTO_TRACK_SUFFIX)
        and to_primary_language(code) == spoken_language
    ]
    return original_codes[0] if original_codes else ""


def _event_text(event: dict[str, Any]) -> str:
    text = "".join(segment.get("utf8", "") for segment in event.get("segs", []))
    return text.replace("\n", LINE_SEPARATOR).strip()
