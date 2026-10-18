from dataclasses import dataclass
from typing import Any

MS_PER_SECOND = 1000
LIVE_CHAT_TRACK_CODE = "live_chat"


@dataclass(frozen=True)
class VideoInfo:
    video_id: str
    title: str
    duration_ms: int
    live_status: str
    metadata_language: str
    manual_caption_codes: list[str]
    auto_caption_codes: list[str]


def info_json_to_video_info(info: dict[str, Any]) -> VideoInfo:
    manual_caption_codes = [
        code for code in (info.get("subtitles") or {}) if code != LIVE_CHAT_TRACK_CODE
    ]
    return VideoInfo(
        video_id=str(info.get("id", "")),
        title=str(info.get("title") or info.get("id", "")),
        duration_ms=int((info.get("duration") or 0) * MS_PER_SECOND),
        live_status=str(info.get("live_status") or ""),
        metadata_language=str(info.get("language") or ""),
        manual_caption_codes=sorted(manual_caption_codes),
        auto_caption_codes=sorted(info.get("automatic_captions") or {}),
    )
