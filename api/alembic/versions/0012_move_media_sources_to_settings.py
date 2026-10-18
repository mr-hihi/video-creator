"""move the image and clip sources of projects and clones to the settings

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("film_projects", "image_source")
    op.drop_column("film_projects", "clip_source")
    op.drop_column("film_clones", "image_source")


def downgrade() -> None:
    op.add_column("film_clones", sa.Column("image_source", sa.String(16), nullable=True))
    op.add_column(
        "film_projects",
        sa.Column("clip_source", sa.String(16), nullable=False, server_default="google_flow"),
    )
    op.add_column(
        "film_projects",
        sa.Column("image_source", sa.String(16), nullable=False, server_default="google_flow"),
    )
