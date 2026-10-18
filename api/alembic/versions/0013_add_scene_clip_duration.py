"""give every scene its own clip length, taken from its project's default

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BACKFILL_SCENE_CLIP_DURATION = """
UPDATE film_scenes SET clip_duration_s = (
    SELECT film_projects.clip_duration_s
    FROM film_episodes
    JOIN film_projects ON film_projects.id = film_episodes.project_id
    WHERE film_episodes.id = film_scenes.episode_id
)
"""


def upgrade() -> None:
    op.add_column("film_scenes", sa.Column("clip_duration_s", sa.Integer(), nullable=True))
    op.execute(sa.text(BACKFILL_SCENE_CLIP_DURATION))
    with op.batch_alter_table("film_scenes") as batch:
        batch.alter_column("clip_duration_s", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    op.drop_column("film_scenes", "clip_duration_s")
