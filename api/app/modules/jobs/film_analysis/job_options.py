from collections.abc import Mapping
from typing import Any

from app.modules.jobs.errors import InvalidFilmAnalysisJobError
from app.modules.jobs.youtube_to_markdown.job_options import (
    CAPTION_KIND_KEY,
    LANGUAGE_KEY,
    URL_KEY,
    VIDEO_ID_KEY,
)

MAX_FRAMES_KEY = "maxFrames"
FRAME_COUNTS_KEY = "frameCounts"
RERUN_OF_JOB_ID_KEY = "rerunOfJobId"
DEFAULT_MAX_FRAMES = 1000
MAX_FRAMES_LOWER_LIMIT = 10
MAX_FRAMES_UPPER_LIMIT = 1000
REUSED_SOURCE_OPTION_KEYS = (
    LANGUAGE_KEY,
    URL_KEY,
    VIDEO_ID_KEY,
    CAPTION_KIND_KEY,
    FRAME_COUNTS_KEY,
)


def to_valid_max_frames(requested_max_frames: int | None) -> int:
    if requested_max_frames is None:
        return DEFAULT_MAX_FRAMES
    if not MAX_FRAMES_LOWER_LIMIT <= requested_max_frames <= MAX_FRAMES_UPPER_LIMIT:
        raise InvalidFilmAnalysisJobError(
            f"Max frames must be between {MAX_FRAMES_LOWER_LIMIT} and {MAX_FRAMES_UPPER_LIMIT}"
        )
    return requested_max_frames


def get_max_frames(options: Mapping[str, Any]) -> int:
    return options.get(MAX_FRAMES_KEY, DEFAULT_MAX_FRAMES)


def copy_reused_source_options(source_options: Mapping[str, Any]) -> dict[str, Any]:
    return {key: source_options[key] for key in REUSED_SOURCE_OPTION_KEYS if key in source_options}
