from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UtcDateTime, build_string_enum_type, utc_now
from app.modules.providers.provider_catalog import MediaKind


class GenerationKind(StrEnum):
    CHARACTER_IMAGE = "character_image"
    SCENE_IMAGE = "scene_image"
    EDIT_IMAGE = "edit_image"
    SCENE_CLIP = "scene_clip"
    NARRATION = "narration"
    MUSIC = "music"
    THUMBNAIL = "thumbnail"
    CLONE_REFERENCE_IMAGE = "clone_reference_image"
    CLONE_SCENE_IMAGE = "clone_scene_image"


class GenerationStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


OPEN_GENERATION_STATUSES = frozenset({GenerationStatus.QUEUED, GenerationStatus.PROCESSING})
CLONE_GENERATION_KINDS = frozenset(
    {GenerationKind.CLONE_REFERENCE_IMAGE, GenerationKind.CLONE_SCENE_IMAGE}
)


class GenerationRequest(Base):
    __tablename__ = "film_generation_requests"
    __table_args__ = (
        Index("ix_film_generation_requests_status_created_at", "status", "created_at"),
        Index("ix_film_generation_requests_clone_id", "clone_id"),
        Index("ix_film_generation_requests_project_id", "project_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[GenerationKind] = mapped_column(build_string_enum_type(GenerationKind, 32))
    media_kind: Mapped[MediaKind] = mapped_column(build_string_enum_type(MediaKind, 16))
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    clone_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    episode_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    scene_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    character_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    clone_asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    clone_scene_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    provider: Mapped[str] = mapped_column(String(20))
    prompt: Mapped[str] = mapped_column(Text)
    input_paths: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[GenerationStatus] = mapped_column(build_string_enum_type(GenerationStatus, 16))
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
