"""add the AI model of a film episode

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "film_episodes",
        sa.Column("ai_model", sa.String(16), nullable=False, server_default="claude"),
    )


def downgrade() -> None:
    op.drop_column("film_episodes", "ai_model")
