"""record the AI model each step used

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AI_USED_TABLES = ("jobs", "film_clones", "film_episodes")
AI_MODEL_KEY = "aiModel"
AI_STEP_MODELS_KEY = "aiStepModels"
LEGACY_GEMINI_VALUE = "gemini"
GEMINI_MODEL_VALUE = {"provider": "google", "model": "gemini-3.8-flash"}

app_settings = sa.table("app_settings", sa.column("key", sa.String), sa.column("value", sa.JSON))


def upgrade() -> None:
    for table_name in AI_USED_TABLES:
        op.add_column(table_name, sa.Column("ai_used", sa.JSON(), nullable=True))
        op.execute(sa.text(f"UPDATE {table_name} SET ai_used = '{{}}'"))
        op.alter_column(table_name, "ai_used", existing_type=sa.JSON(), nullable=False)
    op.drop_column("film_episodes", "ai_model")
    _upgrade_ai_model_setting()


def downgrade() -> None:
    op.execute(app_settings.delete().where(app_settings.c.key.in_([AI_MODEL_KEY, AI_STEP_MODELS_KEY])))
    op.add_column(
        "film_episodes",
        sa.Column("ai_model", sa.String(16), nullable=False, server_default="claude"),
    )
    for table_name in AI_USED_TABLES:
        op.drop_column(table_name, "ai_used")


def _upgrade_ai_model_setting() -> None:
    connection = op.get_bind()
    stored_value = connection.execute(
        sa.select(app_settings.c.value).where(app_settings.c.key == AI_MODEL_KEY)
    ).scalar()
    if stored_value is None or isinstance(stored_value, dict):
        return
    setting = app_settings.c.key == AI_MODEL_KEY
    if stored_value == LEGACY_GEMINI_VALUE:
        connection.execute(app_settings.update().where(setting).values(value=GEMINI_MODEL_VALUE))
        return
    connection.execute(app_settings.delete().where(setting))
