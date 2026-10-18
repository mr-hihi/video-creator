"""create providers and provider routes

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMP_TYPE = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
TABLE_OPTIONS = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}


def upgrade() -> None:
    op.create_table(
        "providers",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("api_key_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("api_key_last4", sa.String(4), nullable=True),
        sa.Column("base_url", sa.String(500), nullable=True),
        sa.Column("models", sa.JSON(), nullable=False),
        sa.Column("max_concurrent", sa.Integer(), nullable=False),
        sa.Column("min_interval_s", sa.Integer(), nullable=False),
        sa.Column("flow_project_id", sa.String(36), nullable=True),
        sa.Column("last_test_at", TIMESTAMP_TYPE, nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column("updated_at", TIMESTAMP_TYPE, nullable=False),
        **TABLE_OPTIONS,
    )
    op.create_table(
        "provider_routes",
        sa.Column("route", sa.String(20), primary_key=True),
        sa.Column("provider_id", sa.String(20), nullable=False),
        sa.Column("updated_at", TIMESTAMP_TYPE, nullable=False),
        **TABLE_OPTIONS,
    )


def downgrade() -> None:
    op.drop_table("provider_routes")
    op.drop_table("providers")
