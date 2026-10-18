"""create film clones

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMP_TYPE = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
LONG_TEXT_TYPE = sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql")
TABLE_OPTIONS = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}


def _clone_id_column() -> sa.Column:
    return sa.Column(
        "clone_id",
        sa.String(36),
        sa.ForeignKey("film_clones.id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "film_clones",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "job_id", sa.String(36), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("step", sa.String(32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("target_country", sa.String(2), nullable=True),
        sa.Column("change_appearance", sa.Boolean(), nullable=False),
        sa.Column("change_costume", sa.Boolean(), nullable=False),
        sa.Column("change_setting", sa.Boolean(), nullable=False),
        sa.Column("image_source", sa.String(16), nullable=True),
        sa.Column("script_language", sa.String(3), nullable=True),
        sa.Column("aspect", sa.String(8), nullable=True),
        sa.Column("script_title", sa.String(150), nullable=True),
        sa.Column("logline", sa.Text(), nullable=True),
        sa.Column("preset", sa.JSON(), nullable=False),
        sa.Column("prompts", sa.JSON(), nullable=False),
        sa.Column("flow_project_id", sa.String(36), nullable=True),
        sa.Column("created_at", TIMESTAMP_TYPE, nullable=False),
        sa.Column("updated_at", TIMESTAMP_TYPE, nullable=False),
        sa.Column("finished_at", TIMESTAMP_TYPE, nullable=True),
        **TABLE_OPTIONS,
    )
    op.create_index("ix_film_clones_status_step", "film_clones", ["status", "step"])
    op.create_index("ix_film_clones_job_id", "film_clones", ["job_id"])
    op.create_table(
        "film_clone_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        _clone_id_column(),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("culture", sa.String(100), nullable=False),
        sa.Column("period", sa.String(100), nullable=False),
        sa.Column("frames", sa.JSON(), nullable=False),
        sa.Column("reference_frame", sa.String(255), nullable=True),
        sa.Column("changed", sa.Boolean(), nullable=False),
        sa.Column("localized_name", sa.String(100), nullable=True),
        sa.Column("localized_description", sa.Text(), nullable=True),
        sa.Column("localization_note", sa.String(300), nullable=True),
        sa.Column("reference_status", sa.String(16), nullable=False),
        sa.Column("reference_path", sa.String(500), nullable=True),
        sa.Column("reference_error", sa.Text(), nullable=True),
        **TABLE_OPTIONS,
    )
    op.create_index("ix_film_clone_assets_clone_id", "film_clone_assets", ["clone_id"])
    op.create_table(
        "film_clone_shots",
        sa.Column("id", sa.String(36), primary_key=True),
        _clone_id_column(),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("at_ms", sa.Integer(), nullable=False),
        sa.Column("frame", sa.String(255), nullable=False),
        sa.Column("frame_kind", sa.String(16), nullable=False),
        sa.Column("shot_size", sa.String(24), nullable=True),
        sa.Column("camera_angle", sa.String(24), nullable=True),
        sa.Column("emotion", sa.String(200), nullable=True),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("asset_ids", sa.JSON(), nullable=False),
        **TABLE_OPTIONS,
    )
    op.create_index("ix_film_clone_shots_clone_id", "film_clone_shots", ["clone_id"])
    op.create_table(
        "film_clone_scenes",
        sa.Column("id", sa.String(36), primary_key=True),
        _clone_id_column(),
        sa.Column(
            "shot_id",
            sa.String(36),
            sa.ForeignKey("film_clone_shots.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("dialogue", sa.Text(), nullable=True),
        sa.Column("image_prompt", LONG_TEXT_TYPE, nullable=False),
        sa.Column("asset_ids", sa.JSON(), nullable=False),
        sa.Column("image_status", sa.String(16), nullable=False),
        sa.Column("image_path", sa.String(500), nullable=True),
        sa.Column("image_error", sa.Text(), nullable=True),
        **TABLE_OPTIONS,
    )
    op.create_index("ix_film_clone_scenes_clone_id", "film_clone_scenes", ["clone_id"])


def downgrade() -> None:
    op.drop_table("film_clone_scenes")
    op.drop_table("film_clone_shots")
    op.drop_table("film_clone_assets")
    op.drop_table("film_clones")
