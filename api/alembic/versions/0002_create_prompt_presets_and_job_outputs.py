"""create prompt presets and job outputs

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMP_TYPE = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
LONG_TEXT_TYPE = sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql")
TABLE_OPTIONS = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}


def upgrade() -> None:
    op.create_table(
        "prompt_presets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("created_at", TIMESTAMP_TYPE, nullable=False),
        sa.Column("updated_at", TIMESTAMP_TYPE, nullable=False),
        **TABLE_OPTIONS,
    )
    op.create_table(
        "prompt_preset_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "preset_id",
            sa.String(36),
            sa.ForeignKey("prompt_presets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("change", sa.String(16), nullable=False),
        sa.Column("change_source", sa.String(120), nullable=True),
        sa.Column("video_to_markdown", LONG_TEXT_TYPE, nullable=False),
        sa.Column("character_image", LONG_TEXT_TYPE, nullable=False),
        sa.Column("character_voice", LONG_TEXT_TYPE, nullable=False),
        sa.Column("scene", LONG_TEXT_TYPE, nullable=False),
        sa.Column("created_at", TIMESTAMP_TYPE, nullable=False),
        sa.UniqueConstraint("preset_id", "version"),
        **TABLE_OPTIONS,
    )
    op.create_table(
        "job_outputs",
        sa.Column(
            "job_id",
            sa.String(36),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("kind", sa.String(32), primary_key=True),
        sa.Column("content", LONG_TEXT_TYPE, nullable=False),
        sa.Column("created_at", TIMESTAMP_TYPE, nullable=False),
        **TABLE_OPTIONS,
    )


def downgrade() -> None:
    op.drop_table("job_outputs")
    op.drop_table("prompt_preset_versions")
    op.drop_table("prompt_presets")
