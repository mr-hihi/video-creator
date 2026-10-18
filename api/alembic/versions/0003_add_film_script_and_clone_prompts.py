"""add film script and film clone prompts to preset versions

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LONG_TEXT_TYPE = sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql")
NEW_PROMPT_COLUMNS = (
    "film_script",
    "clone_assets",
    "clone_shots",
    "clone_localization",
    "clone_script",
)


def upgrade() -> None:
    for column_name in NEW_PROMPT_COLUMNS:
        op.add_column(
            "prompt_preset_versions", sa.Column(column_name, LONG_TEXT_TYPE, nullable=True)
        )


def downgrade() -> None:
    for column_name in reversed(NEW_PROMPT_COLUMNS):
        op.drop_column("prompt_preset_versions", column_name)
