import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

PLAN_FILE_NAME = "plan.json"
SEGMENT_FILE_NAME = "{number}.mp4"
LAST_FRAME_FILE_NAME = "{number}-last.png"
JOINED_FILE_NAME = "joined.mp4"
PARTIAL_SUFFIX = ".part"
TEXT_ENCODING = "utf-8"


class ClipSegmentFolder:
    def __init__(self, directory: Path):
        self._directory = directory

    def ensure_made_from(self, made_from: Mapping[str, Any]) -> None:
        plan_path = self._directory / PLAN_FILE_NAME
        made_from_text = json.dumps(made_from, sort_keys=True)
        if plan_path.exists() and plan_path.read_text(TEXT_ENCODING) == made_from_text:
            return
        self.delete()
        self._directory.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(made_from_text, TEXT_ENCODING)

    def has_segment(self, number: int) -> bool:
        return self.segment_path(number).exists()

    def save_segment(self, number: int, content: bytes) -> None:
        segment_path = self.segment_path(number)
        partial_path = segment_path.with_name(segment_path.name + PARTIAL_SUFFIX)
        partial_path.write_bytes(content)
        partial_path.replace(segment_path)

    def segment_path(self, number: int) -> Path:
        return self._directory / SEGMENT_FILE_NAME.format(number=number)

    def last_frame_path(self, number: int) -> Path:
        return self._directory / LAST_FRAME_FILE_NAME.format(number=number)

    def joined_path(self) -> Path:
        return self._directory / JOINED_FILE_NAME

    def delete(self) -> None:
        shutil.rmtree(self._directory, ignore_errors=True)
