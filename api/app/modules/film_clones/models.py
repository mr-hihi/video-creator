from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import LONG_TEXT_TYPE, Base, UtcDateTime, build_string_enum_type, utc_now
from app.modules.jobs.film_analysis.frames import FrameKind


class CloneStatus(StrEnum):
    RUNNING = "running"
    WAITING = "waiting"
    DONE = "done"
    FAILED = "failed"


class CloneStep(StrEnum):
    ANALYZING = "analyzing"
    EXTRACTING_ASSETS = "extracting_assets"
    ANALYZING_SHOTS = "analyzing_shots"
    CHOOSING_LOCALIZATION = "choosing_localization"
    PROPOSING = "proposing"
    REVIEWING = "reviewing"
    WRITING_SCRIPT = "writing_script"
    GENERATING_SCENE_IMAGES = "generating_scene_images"


class AssetKind(StrEnum):
    CHARACTER = "character"
    COSTUME = "costume"
    PROP = "prop"
    LOCATION = "location"


class ShotSize(StrEnum):
    EXTREME_WIDE = "extreme_wide"
    WIDE = "wide"
    FULL = "full"
    MEDIUM = "medium"
    MEDIUM_CLOSE = "medium_close"
    CLOSE_UP = "close_up"
    EXTREME_CLOSE_UP = "extreme_close_up"


class CameraAngle(StrEnum):
    EYE_LEVEL = "eye_level"
    HIGH = "high"
    LOW = "low"
    BIRDS_EYE = "birds_eye"
    WORMS_EYE = "worms_eye"
    DUTCH = "dutch"
    OVER_THE_SHOULDER = "over_the_shoulder"
    POV = "pov"


class CloneImageStatus(StrEnum):
    NONE = "none"
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class CloneAspect(StrEnum):
    LANDSCAPE = "16:9"
    PORTRAIT = "9:16"


class FilmClone(Base):
    __tablename__ = "film_clones"
    __table_args__ = (Index("ix_film_clones_status_step", "status", "step"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[CloneStatus] = mapped_column(build_string_enum_type(CloneStatus, 16))
    step: Mapped[CloneStep] = mapped_column(build_string_enum_type(CloneStep, 32))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    target_setting: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_appearance: Mapped[bool] = mapped_column(Boolean, default=False)
    change_costume: Mapped[bool] = mapped_column(Boolean, default=False)
    change_setting: Mapped[bool] = mapped_column(Boolean, default=False)
    should_run_automatically: Mapped[bool] = mapped_column(Boolean, default=False)
    script_language: Mapped[str | None] = mapped_column(String(3), nullable=True)
    aspect: Mapped[CloneAspect | None] = mapped_column(
        build_string_enum_type(CloneAspect, 8), nullable=True
    )
    script_title: Mapped[str | None] = mapped_column(String(150), nullable=True)
    logline: Mapped[str | None] = mapped_column(Text, nullable=True)
    preset: Mapped[dict[str, Any]] = mapped_column(JSON)
    prompts: Mapped[dict[str, Any]] = mapped_column(JSON)
    ai_used: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    flow_project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)


class CloneAsset(Base):
    __tablename__ = "film_clone_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    clone_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("film_clones.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[AssetKind] = mapped_column(build_string_enum_type(AssetKind, 16))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    culture: Mapped[str] = mapped_column(String(100))
    period: Mapped[str] = mapped_column(String(100))
    frames: Mapped[list[str]] = mapped_column(JSON, default=list)
    reference_frame: Mapped[str | None] = mapped_column(String(255), nullable=True)
    changed: Mapped[bool] = mapped_column(Boolean, default=False)
    localized_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    localized_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    localization_note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    reference_status: Mapped[CloneImageStatus] = mapped_column(
        build_string_enum_type(CloneImageStatus, 16), default=CloneImageStatus.NONE
    )
    reference_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reference_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class CloneShot(Base):
    __tablename__ = "film_clone_shots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    clone_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("film_clones.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    at_ms: Mapped[int] = mapped_column(Integer)
    frame: Mapped[str] = mapped_column(String(255))
    frame_kind: Mapped[FrameKind] = mapped_column(build_string_enum_type(FrameKind, 16))
    shot_size: Mapped[ShotSize | None] = mapped_column(
        build_string_enum_type(ShotSize, 24), nullable=True
    )
    camera_angle: Mapped[CameraAngle | None] = mapped_column(
        build_string_enum_type(CameraAngle, 24), nullable=True
    )
    emotion: Mapped[str | None] = mapped_column(String(200), nullable=True)
    action: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset_ids: Mapped[list[str]] = mapped_column(JSON, default=list)


class CloneScene(Base):
    __tablename__ = "film_clone_scenes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    clone_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("film_clones.id", ondelete="CASCADE"), index=True
    )
    shot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("film_clone_shots.id", ondelete="CASCADE"), unique=True
    )
    position: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    dialogue: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_prompt: Mapped[str] = mapped_column(LONG_TEXT_TYPE)
    asset_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    image_status: Mapped[CloneImageStatus] = mapped_column(
        build_string_enum_type(CloneImageStatus, 16), default=CloneImageStatus.NONE
    )
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_error: Mapped[str | None] = mapped_column(Text, nullable=True)
