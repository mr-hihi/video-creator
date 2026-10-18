"""create film studio

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMP_TYPE = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
LONG_TEXT_TYPE = sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql")
TABLE_OPTIONS = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", TIMESTAMP_TYPE, nullable=False),
        sa.Column("updated_at", TIMESTAMP_TYPE, nullable=False),
    ]


def _media_status_columns(*prefixes: str) -> list[sa.Column]:
    return [sa.Column(f"{prefix}_status", sa.String(16), nullable=False) for prefix in prefixes]


def upgrade() -> None:
    op.create_table(
        "film_styles",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=False),
        sa.Column("style_instruction", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column("scene_prefix", sa.Text(), nullable=True),
        sa.Column("lighting", sa.String(200), nullable=False),
        *_timestamps(),
        **TABLE_OPTIONS,
    )
    op.create_table(
        "film_voice_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("sample_path", sa.String(500), nullable=False),
        sa.Column("sample_text", sa.Text(), nullable=False),
        sa.Column("sample_duration_ms", sa.Integer(), nullable=False),
        sa.Column("consent_path", sa.String(500), nullable=True),
        sa.Column("provider_voices", sa.JSON(), nullable=False),
        *_timestamps(),
        **TABLE_OPTIONS,
    )
    op.create_table(
        "film_projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("language", sa.String(2), nullable=False),
        sa.Column("orientation", sa.String(16), nullable=False),
        sa.Column("style_id", sa.String(40), sa.ForeignKey("film_styles.id"), nullable=False),
        sa.Column("image_source", sa.String(16), nullable=False),
        sa.Column("clip_source", sa.String(16), nullable=False),
        sa.Column("clip_duration_s", sa.Integer(), nullable=False),
        sa.Column("allow_dialogue", sa.Boolean(), nullable=False),
        sa.Column("allow_narration", sa.Boolean(), nullable=False),
        sa.Column(
            "narrator_voice_id",
            sa.String(36),
            sa.ForeignKey("film_voice_templates.id"),
            nullable=True,
        ),
        sa.Column("allow_music", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("last_episode_number", sa.Integer(), nullable=False),
        sa.Column("flow_project_id", sa.String(36), nullable=True),
        *_timestamps(),
        **TABLE_OPTIONS,
    )
    op.create_table(
        "film_characters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("entity_type", sa.String(16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("image_prompt", sa.Text(), nullable=False),
        sa.Column("voice_description", sa.String(300), nullable=True),
        sa.Column("style_id", sa.String(40), sa.ForeignKey("film_styles.id"), nullable=False),
        *_media_status_columns("reference"),
        sa.Column("reference_source", sa.String(16), nullable=True),
        sa.Column("reference_path", sa.String(500), nullable=True),
        sa.Column("reference_error", sa.Text(), nullable=True),
        sa.Column("provider_media", sa.JSON(), nullable=True),
        sa.Column("origin_job_id", sa.String(36), nullable=True),
        sa.Column("origin_clone_id", sa.String(36), nullable=True),
        *_timestamps(),
        **TABLE_OPTIONS,
    )
    op.create_table(
        "film_project_characters",
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("film_projects.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "character_id",
            sa.String(36),
            sa.ForeignKey("film_characters.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("created_at", TIMESTAMP_TYPE, nullable=False),
        **TABLE_OPTIONS,
    )
    op.create_table(
        "film_episodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("film_projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("logline", sa.Text(), nullable=True),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("idea", sa.Text(), nullable=True),
        sa.Column("source_job_id", sa.String(36), nullable=True),
        sa.Column("source_clone_id", sa.String(36), nullable=True),
        sa.Column("target_duration_s", sa.Integer(), nullable=False),
        sa.Column("stop_points", sa.JSON(), nullable=False),
        sa.Column("paused_stop_point", sa.String(32), nullable=True),
        sa.Column("burn_subtitles", sa.Boolean(), nullable=False),
        sa.Column("subtitle_style", sa.String(16), nullable=False),
        sa.Column("music_prompt", sa.Text(), nullable=True),
        sa.Column("thumbnail_prompt", sa.Text(), nullable=True),
        *_media_status_columns("music"),
        sa.Column("music_path", sa.String(500), nullable=True),
        sa.Column("music_error", sa.Text(), nullable=True),
        sa.Column("preset", sa.JSON(), nullable=False),
        sa.Column("film_script_prompt", LONG_TEXT_TYPE, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("step", sa.String(32), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("needs_assembly", sa.Boolean(), nullable=False),
        sa.Column("video_path", sa.String(500), nullable=True),
        sa.Column("subtitles_path", sa.String(500), nullable=True),
        sa.Column("thumbnail_path", sa.String(500), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        *_timestamps(),
        sa.Column("started_at", TIMESTAMP_TYPE, nullable=True),
        sa.Column("finished_at", TIMESTAMP_TYPE, nullable=True),
        sa.UniqueConstraint("project_id", "number", name="uq_film_episodes_number"),
        **TABLE_OPTIONS,
    )
    op.create_table(
        "film_scenes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "episode_id",
            sa.String(36),
            sa.ForeignKey("film_episodes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("image_prompt", sa.Text(), nullable=False),
        sa.Column("video_prompt", sa.Text(), nullable=False),
        sa.Column("narrator_text", sa.Text(), nullable=True),
        sa.Column("character_ids", sa.JSON(), nullable=False),
        *_media_status_columns("image", "clip", "narration"),
        sa.Column("image_source", sa.String(16), nullable=True),
        sa.Column("image_path", sa.String(500), nullable=True),
        sa.Column("clip_path", sa.String(500), nullable=True),
        sa.Column("narration_path", sa.String(500), nullable=True),
        sa.Column("image_error", sa.Text(), nullable=True),
        sa.Column("clip_error", sa.Text(), nullable=True),
        sa.Column("narration_error", sa.Text(), nullable=True),
        sa.Column("clip_duration_ms", sa.Integer(), nullable=True),
        sa.Column("narration_duration_ms", sa.Integer(), nullable=True),
        sa.Column("trim_start_ms", sa.Integer(), nullable=False),
        sa.Column("trim_end_ms", sa.Integer(), nullable=True),
        sa.Column("provider_media", sa.JSON(), nullable=True),
        *_timestamps(),
        **TABLE_OPTIONS,
    )


def downgrade() -> None:
    op.drop_table("film_scenes")
    op.drop_table("film_episodes")
    op.drop_table("film_project_characters")
    op.drop_table("film_characters")
    op.drop_table("film_projects")
    op.drop_table("film_voice_templates")
    op.drop_table("film_styles")
