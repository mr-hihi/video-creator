"""split episodes into parts; add the story bible, the episode summary and their prompts

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-19
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from itertools import groupby
from operator import itemgetter
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMP_TYPE = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
LONG_TEXT_TYPE = sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql")
TABLE_OPTIONS = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}
PART_SCENE_LIMIT = 80
CUT_HEAD_S = 1
PART_TITLE = "Part {number}"
PART_PLAN = "Scenes {first}-{last}."
WRITING_OUTLINE = "writing_outline"
WRITING_SCRIPT = "writing_script"
UPDATING_STORY_BIBLE = "updating_story_bible"
PART_ID_INDEX = "ix_film_scenes_part_id"
PART_ID_FOREIGN_KEY = "fk_film_scenes_part_id"

scenes_table = sa.table(
    "film_scenes",
    sa.column("id", sa.String),
    sa.column("episode_id", sa.String),
    sa.column("part_id", sa.String),
    sa.column("position", sa.Integer),
    sa.column("clip_duration_s", sa.Integer),
)
parts_table = sa.table(
    "film_episode_parts",
    sa.column("id", sa.String),
    sa.column("episode_id", sa.String),
    sa.column("position", sa.Integer),
    sa.column("title", sa.String),
    sa.column("plan", sa.Text),
    sa.column("target_duration_s", sa.Integer),
    sa.column("recap", sa.Text),
    sa.column("created_at", sa.DateTime),
    sa.column("updated_at", sa.DateTime),
)
episodes_table = sa.table(
    "film_episodes",
    sa.column("id", sa.String),
    sa.column("step", sa.String),
    sa.column("paused_stop_point", sa.String),
)


def upgrade() -> None:
    op.add_column("film_projects", sa.Column("story_bible", LONG_TEXT_TYPE, nullable=True))
    op.add_column(
        "film_projects", sa.Column("story_bible_episode_id", sa.String(36), nullable=True)
    )
    op.add_column(
        "film_projects", sa.Column("story_bible_updated_at", TIMESTAMP_TYPE, nullable=True)
    )
    op.add_column("film_episodes", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("film_episodes", sa.Column("film_outline_prompt", LONG_TEXT_TYPE, nullable=True))
    op.add_column("film_episodes", sa.Column("story_bible_prompt", LONG_TEXT_TYPE, nullable=True))
    op.add_column(
        "prompt_preset_versions", sa.Column("film_outline", LONG_TEXT_TYPE, nullable=True)
    )
    op.add_column("prompt_preset_versions", sa.Column("story_bible", LONG_TEXT_TYPE, nullable=True))
    op.create_table(
        "film_episode_parts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "episode_id",
            sa.String(36),
            sa.ForeignKey("film_episodes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("plan", sa.Text(), nullable=False),
        sa.Column("target_duration_s", sa.Integer(), nullable=False),
        sa.Column("recap", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP_TYPE, nullable=False),
        sa.Column("updated_at", TIMESTAMP_TYPE, nullable=False),
        **TABLE_OPTIONS,
    )
    op.add_column("film_scenes", sa.Column("part_id", sa.String(36), nullable=True))
    _split_scenes_into_parts()
    with op.batch_alter_table("film_scenes") as batch:
        batch.alter_column("part_id", existing_type=sa.String(36), nullable=False)
        batch.create_index(PART_ID_INDEX, ["part_id"])
        batch.create_foreign_key(
            PART_ID_FOREIGN_KEY, "film_episode_parts", ["part_id"], ["id"], ondelete="CASCADE"
        )
    op.execute(
        episodes_table.update()
        .where(episodes_table.c.step == WRITING_SCRIPT)
        .where(episodes_table.c.id.not_in(sa.select(scenes_table.c.episode_id)))
        .values(step=WRITING_OUTLINE)
    )


def downgrade() -> None:
    _number_scenes_across_episodes()
    for new_step in (WRITING_OUTLINE, UPDATING_STORY_BIBLE):
        op.execute(
            episodes_table.update()
            .where(episodes_table.c.step == new_step)
            .values(step=WRITING_SCRIPT)
        )
        op.execute(
            episodes_table.update()
            .where(episodes_table.c.paused_stop_point == new_step)
            .values(paused_stop_point=WRITING_SCRIPT)
        )
    with op.batch_alter_table("film_scenes") as batch:
        batch.drop_constraint(PART_ID_FOREIGN_KEY, type_="foreignkey")
        batch.drop_index(PART_ID_INDEX)
        batch.drop_column("part_id")
    op.drop_table("film_episode_parts")
    op.drop_column("prompt_preset_versions", "story_bible")
    op.drop_column("prompt_preset_versions", "film_outline")
    op.drop_column("film_episodes", "story_bible_prompt")
    op.drop_column("film_episodes", "film_outline_prompt")
    op.drop_column("film_episodes", "summary")
    op.drop_column("film_projects", "story_bible_updated_at")
    op.drop_column("film_projects", "story_bible_episode_id")
    op.drop_column("film_projects", "story_bible")


def _split_scenes_into_parts() -> None:
    connection = op.get_bind()
    scene_rows = connection.execute(
        sa.select(
            scenes_table.c.id,
            scenes_table.c.episode_id,
            scenes_table.c.clip_duration_s,
        ).order_by(scenes_table.c.episode_id, scenes_table.c.position)
    ).all()
    now = datetime.now(UTC)
    for episode_id, episode_scenes in groupby(scene_rows, key=itemgetter(1)):
        ordered_scenes = list(episode_scenes)
        for part_position, first in enumerate(range(0, len(ordered_scenes), PART_SCENE_LIMIT)):
            part_scenes = ordered_scenes[first : first + PART_SCENE_LIMIT]
            part_id = str(uuid4())
            op.bulk_insert(
                parts_table,
                [_to_part_row(part_id, episode_id, part_position, first, part_scenes, now)],
            )
            for scene_position, scene in enumerate(part_scenes):
                connection.execute(
                    scenes_table.update()
                    .where(scenes_table.c.id == scene.id)
                    .values(part_id=part_id, position=scene_position)
                )


def _to_part_row(
    part_id: str,
    episode_id: str,
    part_position: int,
    first: int,
    part_scenes: Sequence[Any],
    now: datetime,
) -> dict[str, Any]:
    return {
        "id": part_id,
        "episode_id": episode_id,
        "position": part_position,
        "title": PART_TITLE.format(number=part_position + 1),
        "plan": PART_PLAN.format(first=first + 1, last=first + len(part_scenes)),
        "target_duration_s": sum(scene.clip_duration_s - CUT_HEAD_S for scene in part_scenes),
        "recap": None,
        "created_at": now,
        "updated_at": now,
    }


def _number_scenes_across_episodes() -> None:
    connection = op.get_bind()
    scene_rows = connection.execute(
        sa.select(scenes_table.c.id, scenes_table.c.episode_id)
        .select_from(scenes_table.join(parts_table, parts_table.c.id == scenes_table.c.part_id))
        .order_by(scenes_table.c.episode_id, parts_table.c.position, scenes_table.c.position)
    ).all()
    for _, episode_scenes in groupby(scene_rows, key=itemgetter(1)):
        for position, scene in enumerate(episode_scenes):
            connection.execute(
                scenes_table.update().where(scenes_table.c.id == scene.id).values(position=position)
            )
