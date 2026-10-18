from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import LONG_TEXT_TYPE, Base, UtcDateTime, build_string_enum_type, utc_now


class FilmLanguage(StrEnum):
    VIETNAMESE = "vi"
    ENGLISH = "en"
    JAPANESE = "ja"


class Orientation(StrEnum):
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class EntityType(StrEnum):
    CHARACTER = "character"
    LOCATION = "location"
    CREATURE = "creature"
    VISUAL_ASSET = "visual_asset"
    GENERIC_TROOP = "generic_troop"
    FACTION = "faction"


class MediaStatus(StrEnum):
    NONE = "none"
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class ReferenceSource(StrEnum):
    GENERATED = "generated"
    EDITED = "edited"
    UPLOADED = "uploaded"
    FILM_ANALYSIS = "film_analysis"
    FILM_CLONE = "film_clone"


class SceneImageSource(StrEnum):
    GENERATED = "generated"
    EDITED = "edited"
    UPLOADED = "uploaded"
    FILM_CLONE = "film_clone"


class EpisodeSource(StrEnum):
    IDEA = "idea"
    FILM_ANALYSIS = "film_analysis"
    FILM_CLONE = "film_clone"


class EpisodeStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    DONE = "done"
    FAILED = "failed"


class EpisodeStep(StrEnum):
    WRITING_SCRIPT = "writing_script"
    GENERATING_REFERENCES = "generating_references"
    GENERATING_SCENE_IMAGES = "generating_scene_images"
    GENERATING_CLIPS = "generating_clips"
    GENERATING_AUDIO = "generating_audio"
    ASSEMBLING = "assembling"


class SubtitleStyle(StrEnum):
    CLEAN_WHITE = "clean_white"
    CINEMATIC_GOLD = "cinematic_gold"
    CYBER_AMBER = "cyber_amber"
    EMERALD_HUD = "emerald_hud"


OPEN_MEDIA_STATUSES = frozenset({MediaStatus.QUEUED, MediaStatus.PROCESSING})
MISSING_MEDIA_STATUSES = frozenset({MediaStatus.NONE, MediaStatus.FAILED})


class Style(Base):
    __tablename__ = "film_styles"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    style_instruction: Mapped[str] = mapped_column(Text)
    negative_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    scene_prefix: Mapped[str | None] = mapped_column(Text, nullable=True)
    lighting: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)


class VoiceTemplate(Base):
    __tablename__ = "film_voice_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sample_path: Mapped[str] = mapped_column(String(500))
    sample_text: Mapped[str] = mapped_column(Text)
    sample_duration_ms: Mapped[int] = mapped_column(Integer)
    consent_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provider_voices: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)


class FilmProject(Base):
    __tablename__ = "film_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[FilmLanguage] = mapped_column(build_string_enum_type(FilmLanguage, 2))
    orientation: Mapped[Orientation] = mapped_column(build_string_enum_type(Orientation, 16))
    style_id: Mapped[str] = mapped_column(String(40), ForeignKey("film_styles.id"))
    clip_duration_s: Mapped[int] = mapped_column(Integer)
    allow_dialogue: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_narration: Mapped[bool] = mapped_column(Boolean, default=True)
    narrator_voice_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("film_voice_templates.id"), nullable=True
    )
    allow_music: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[ProjectStatus] = mapped_column(build_string_enum_type(ProjectStatus, 16))
    last_episode_number: Mapped[int] = mapped_column(Integer, default=0)
    flow_project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)


class Character(Base):
    __tablename__ = "film_characters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    entity_type: Mapped[EntityType] = mapped_column(build_string_enum_type(EntityType, 16))
    description: Mapped[str] = mapped_column(Text)
    image_prompt: Mapped[str] = mapped_column(Text)
    voice_description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    style_id: Mapped[str] = mapped_column(String(40), ForeignKey("film_styles.id"))
    reference_status: Mapped[MediaStatus] = mapped_column(
        build_string_enum_type(MediaStatus, 16), default=MediaStatus.NONE
    )
    reference_source: Mapped[ReferenceSource | None] = mapped_column(
        build_string_enum_type(ReferenceSource, 16), nullable=True
    )
    reference_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reference_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_media: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    origin_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    origin_clone_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)


class FilmProjectCharacter(Base):
    __tablename__ = "film_project_characters"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("film_projects.id", ondelete="CASCADE"), primary_key=True
    )
    character_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("film_characters.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)


class Episode(Base):
    __tablename__ = "film_episodes"
    __table_args__ = (UniqueConstraint("project_id", "number", name="uq_film_episodes_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("film_projects.id", ondelete="CASCADE"), index=True
    )
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(150))
    logline: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[EpisodeSource] = mapped_column(build_string_enum_type(EpisodeSource, 16))
    idea: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_clone_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    target_duration_s: Mapped[int] = mapped_column(Integer)
    stop_points: Mapped[dict[str, Any]] = mapped_column(JSON)
    paused_stop_point: Mapped[EpisodeStep | None] = mapped_column(
        build_string_enum_type(EpisodeStep, 32), nullable=True
    )
    burn_subtitles: Mapped[bool] = mapped_column(Boolean, default=False)
    subtitle_style: Mapped[SubtitleStyle] = mapped_column(
        build_string_enum_type(SubtitleStyle, 16), default=SubtitleStyle.CLEAN_WHITE
    )
    music_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    music_status: Mapped[MediaStatus] = mapped_column(
        build_string_enum_type(MediaStatus, 16), default=MediaStatus.NONE
    )
    music_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    music_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    preset: Mapped[dict[str, Any]] = mapped_column(JSON)
    film_script_prompt: Mapped[str] = mapped_column(LONG_TEXT_TYPE)
    ai_used: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[EpisodeStatus] = mapped_column(build_string_enum_type(EpisodeStatus, 16))
    step: Mapped[EpisodeStep | None] = mapped_column(
        build_string_enum_type(EpisodeStep, 32), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs_assembly: Mapped[bool] = mapped_column(Boolean, default=False)
    video_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    subtitles_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)


class Scene(Base):
    __tablename__ = "film_scenes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    episode_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("film_episodes.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    image_prompt: Mapped[str] = mapped_column(Text)
    video_prompt: Mapped[str] = mapped_column(Text)
    narrator_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    character_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    clip_duration_s: Mapped[int] = mapped_column(Integer)
    image_status: Mapped[MediaStatus] = mapped_column(
        build_string_enum_type(MediaStatus, 16), default=MediaStatus.NONE
    )
    clip_status: Mapped[MediaStatus] = mapped_column(
        build_string_enum_type(MediaStatus, 16), default=MediaStatus.NONE
    )
    narration_status: Mapped[MediaStatus] = mapped_column(
        build_string_enum_type(MediaStatus, 16), default=MediaStatus.NONE
    )
    image_source: Mapped[SceneImageSource | None] = mapped_column(
        build_string_enum_type(SceneImageSource, 16), nullable=True
    )
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    clip_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    narration_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    clip_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    narration_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    clip_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    narration_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trim_start_ms: Mapped[int] = mapped_column(Integer, default=1000)
    trim_end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_media: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)
