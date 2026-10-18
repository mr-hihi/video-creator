from typing import Any

from app.modules.films.models import MediaStatus

DEFAULT_TRIM_START_MS = 1000

NEW_CLIP_RESET: dict[str, Any] = {"trim_start_ms": DEFAULT_TRIM_START_MS, "trim_end_ms": None}
NEW_IMAGE_RESET: dict[str, Any] = {
    "clip_status": MediaStatus.NONE,
    "clip_path": None,
    "clip_duration_ms": None,
    **NEW_CLIP_RESET,
}
NARRATION_RESET: dict[str, Any] = {
    "narration_status": MediaStatus.NONE,
    "narration_path": None,
    "narration_duration_ms": None,
}
