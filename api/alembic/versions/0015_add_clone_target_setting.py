"""let a film clone carry the free-text setting the user wants

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("film_clones", sa.Column("target_setting", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("film_clones", "target_setting")
