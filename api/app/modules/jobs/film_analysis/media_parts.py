from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import accumulate
from pathlib import Path

from app.modules.jobs.video_to_markdown.transcript import TranscriptSegment, format_timestamp

PART_FILE_GLOB = "part-*"
AUDIO_MIME_TYPE = "audio/mp4"
VIDEO_MIME_TYPE = "video/mp4"
AUDIO_MEDIA_WORD = "audio"
VIDEO_MEDIA_WORD = "video"


@dataclass(frozen=True)
class MediaPart:
    path: Path
    start_ms: int
    end_ms: int


def find_part_paths(parts_dir: Path) -> list[Path]:
    return sorted(path for path in parts_dir.glob(PART_FILE_GLOB) if path.is_file())


def to_media_parts(part_paths: Sequence[Path], durations_ms: Sequence[int]) -> list[MediaPart]:
    end_times_ms = list(accumulate(durations_ms))
    start_times_ms = [0, *end_times_ms][:-1]
    return [
        MediaPart(path=path, start_ms=start_ms, end_ms=end_ms)
        for path, start_ms, end_ms in zip(part_paths, start_times_ms, end_times_ms, strict=True)
    ]


def group_segments_by_part(
    segments: Sequence[TranscriptSegment], parts: Sequence[MediaPart]
) -> list[list[TranscriptSegment]]:
    part_starts_ms = [part.start_ms for part in parts]
    grouped: list[list[TranscriptSegment]] = [[] for _ in parts]
    for segment in segments:
        part_index = max(bisect_right(part_starts_ms, segment.start_ms) - 1, 0)
        grouped[part_index].append(segment)
    return grouped


def to_part_label(media_word: str, part: MediaPart) -> str:
    return f"[{media_word} {format_timestamp(part.start_ms)}–{format_timestamp(part.end_ms)}]"
