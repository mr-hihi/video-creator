from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class SegmentJoin:
    segment_paths: tuple[Path, ...]
    output_path: Path
    clip_length_s: int
    has_sound: bool


class ClipEditor(Protocol):
    def save_last_frame(self, clip_path: Path, frame_path: Path) -> None: ...

    def join_segments(self, join: SegmentJoin) -> None: ...
