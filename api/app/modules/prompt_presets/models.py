from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import LONG_TEXT_TYPE, Base, UtcDateTime, build_string_enum_type, utc_now
from app.modules.prompt_presets.prompt_texts import (
    DEFAULT_PRESET_PROMPTS,
    PRESET_PROMPT_FIELD_NAMES,
    PresetPrompts,
)


class PresetChange(StrEnum):
    CREATED = "created"
    SAVED = "saved"
    RESTORED = "restored"
    DUPLICATED = "duplicated"
    IMPORTED = "imported"


class PromptPreset(Base):
    __tablename__ = "prompt_presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    current_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)


class PromptPresetVersion(Base):
    __tablename__ = "prompt_preset_versions"
    __table_args__ = (UniqueConstraint("preset_id", "version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    preset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("prompt_presets.id", ondelete="CASCADE")
    )
    version: Mapped[int] = mapped_column(Integer)
    change: Mapped[PresetChange] = mapped_column(build_string_enum_type(PresetChange, 16))
    change_source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    video_to_markdown: Mapped[str] = mapped_column(LONG_TEXT_TYPE)
    speakers_and_sounds: Mapped[str | None] = mapped_column(LONG_TEXT_TYPE, nullable=True)
    character_image: Mapped[str] = mapped_column(LONG_TEXT_TYPE)
    character_voice: Mapped[str] = mapped_column(LONG_TEXT_TYPE)
    scene: Mapped[str] = mapped_column(LONG_TEXT_TYPE)
    film_outline: Mapped[str | None] = mapped_column(LONG_TEXT_TYPE, nullable=True)
    film_script: Mapped[str | None] = mapped_column(LONG_TEXT_TYPE, nullable=True)
    story_bible: Mapped[str | None] = mapped_column(LONG_TEXT_TYPE, nullable=True)
    clone_assets: Mapped[str | None] = mapped_column(LONG_TEXT_TYPE, nullable=True)
    clone_shots: Mapped[str | None] = mapped_column(LONG_TEXT_TYPE, nullable=True)
    clone_localization: Mapped[str | None] = mapped_column(LONG_TEXT_TYPE, nullable=True)
    clone_script: Mapped[str | None] = mapped_column(LONG_TEXT_TYPE, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now)

    def to_preset_prompts(self) -> PresetPrompts:
        # Versions written before a prompt existed hold NULL for it and read its code default.
        return PresetPrompts(
            **{
                field_name: getattr(self, field_name) or getattr(DEFAULT_PRESET_PROMPTS, field_name)
                for field_name in PRESET_PROMPT_FIELD_NAMES
            }
        )
