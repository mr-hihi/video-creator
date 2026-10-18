from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import LONG_TEXT_TYPE, Base, UtcDateTime, build_string_enum_type, utc_now


class JobType(StrEnum):
    VIDEO_TO_MARKDOWN = "video_to_markdown"
    YOUTUBE_TO_MARKDOWN = "youtube_to_markdown"
    FILM_ANALYSIS = "film_analysis"
    YOUTUBE_FILM_ANALYSIS = "youtube_film_analysis"
    FILM_ANALYSIS_RERUN = "film_analysis_rerun"
    FILM_CLONE = "film_clone"
    YOUTUBE_FILM_CLONE = "youtube_film_clone"


FILM_ANALYSIS_JOB_TYPES = frozenset(
    {JobType.FILM_ANALYSIS, JobType.YOUTUBE_FILM_ANALYSIS, JobType.FILM_ANALYSIS_RERUN}
)
FILM_CLONE_JOB_TYPES = frozenset({JobType.FILM_CLONE, JobType.YOUTUBE_FILM_CLONE})
VIDEO_NOTES_JOB_TYPES = FILM_ANALYSIS_JOB_TYPES | FILM_CLONE_JOB_TYPES


class JobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


FINISHED_JOB_STATUSES = frozenset({JobStatus.DONE, JobStatus.FAILED})


class JobStep(StrEnum):
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    FETCHING_TRANSCRIPT = "fetching_transcript"
    PICKING_MOMENTS = "picking_moments"
    DOWNLOADING_VIDEO = "downloading_video"
    SAMPLING_FRAMES = "sampling_frames"
    DETECTING_SCENES = "detecting_scenes"
    CAPTURING_FRAMES = "capturing_frames"
    WRITING_MARKDOWN = "writing_markdown"
    WRITING_CHARACTER_IMAGE_PROMPTS = "writing_character_image_prompts"
    WRITING_CHARACTER_VOICE_PROMPTS = "writing_character_voice_prompts"
    WRITING_SCENE_PROMPTS = "writing_scene_prompts"
    EXTRACTING_ASSETS = "extracting_assets"
    ANALYZING_SHOTS = "analyzing_shots"


class JobOutputKind(StrEnum):
    VIDEO_NOTES = "video_notes"
    CHARACTER_IMAGE_PROMPTS = "character_image_prompts"
    CHARACTER_VOICE_PROMPTS = "character_voice_prompts"
    SCENE_PROMPTS = "scene_prompts"


PROMPT_OUTPUT_KINDS = frozenset(
    {
        JobOutputKind.CHARACTER_IMAGE_PROMPTS,
        JobOutputKind.CHARACTER_VOICE_PROMPTS,
        JobOutputKind.SCENE_PROMPTS,
    }
)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_status_created_at", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[JobType] = mapped_column(build_string_enum_type(JobType, 32))
    status: Mapped[JobStatus] = mapped_column(build_string_enum_type(JobStatus, 16))
    step: Mapped[JobStep | None] = mapped_column(build_string_enum_type(JobStep, 32), nullable=True)
    source_filename: Mapped[str] = mapped_column(String(255))
    options: Mapped[dict[str, Any]] = mapped_column(JSON)
    ai_used: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)


class JobOutput(Base):
    __tablename__ = "job_outputs"

    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[JobOutputKind] = mapped_column(
        build_string_enum_type(JobOutputKind, 32), primary_key=True
    )
    content: Mapped[str] = mapped_column(LONG_TEXT_TYPE)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
