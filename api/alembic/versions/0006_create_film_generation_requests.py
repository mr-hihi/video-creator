"""create film generation requests

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMP_TYPE = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
TABLE_OPTIONS = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}
TARGET_ID_COLUMNS = (
    "project_id",
    "clone_id",
    "episode_id",
    "scene_id",
    "character_id",
    "clone_asset_id",
    "clone_scene_id",
)


def upgrade() -> None:
    op.create_table(
        "film_generation_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("media_kind", sa.String(16), nullable=False),
        *(sa.Column(column_name, sa.String(36), nullable=True) for column_name in TARGET_ID_COLUMNS),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("input_paths", sa.JSON(), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", TIMESTAMP_TYPE, nullable=True),
        sa.Column("output_path", sa.String(500), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP_TYPE, nullable=False),
        sa.Column("started_at", TIMESTAMP_TYPE, nullable=True),
        sa.Column("finished_at", TIMESTAMP_TYPE, nullable=True),
        **TABLE_OPTIONS,
    )
    op.create_index(
        "ix_film_generation_requests_status_created_at",
        "film_generation_requests",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_film_generation_requests_clone_id", "film_generation_requests", ["clone_id"]
    )
    op.create_index(
        "ix_film_generation_requests_project_id", "film_generation_requests", ["project_id"]
    )


def downgrade() -> None:
    op.drop_table("film_generation_requests")
