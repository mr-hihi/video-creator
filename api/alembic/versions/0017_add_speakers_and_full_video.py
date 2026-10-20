"""add the speakers and sounds prompt; give Film Analysis its own input mode

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-20
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

from app.modules.prompt_presets.prompt_texts import DEFAULT_PRESET_PROMPTS

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LONG_TEXT_TYPE = sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql")
SPEAKERS_AND_SOUNDS_COLUMN = "speakers_and_sounds"
INPUT_MODE_KEY = "inputMode"
FILM_ANALYSIS_INPUT_MODE_KEY = "filmAnalysisInputMode"
AI_STEP_MODELS_KEY = "aiStepModels"
AUDIO_GROUP = "audio"
NEW_JOB_STEPS = ("listening_to_audio", "compressing_video")
SOUND_FRAME_KIND = "sound"
DIALOGUE_FRAME_KIND = "dialogue"

app_settings = sa.table(
    "app_settings",
    sa.column("key", sa.String),
    sa.column("value", sa.JSON),
    sa.column("updated_at", sa.DateTime),
)
preset_versions = sa.table(
    "prompt_preset_versions",
    sa.column(SPEAKERS_AND_SOUNDS_COLUMN, sa.Text),
)
jobs = sa.table("jobs", sa.column("step", sa.String))
clone_shots = sa.table("film_clone_shots", sa.column("frame_kind", sa.String))


def upgrade() -> None:
    op.add_column(
        "prompt_preset_versions",
        sa.Column(SPEAKERS_AND_SOUNDS_COLUMN, LONG_TEXT_TYPE, nullable=True),
    )
    op.execute(
        preset_versions.update().values(
            {SPEAKERS_AND_SOUNDS_COLUMN: DEFAULT_PRESET_PROMPTS.speakers_and_sounds}
        )
    )
    input_mode = _find_setting(INPUT_MODE_KEY)
    if input_mode is not None and _find_setting(FILM_ANALYSIS_INPUT_MODE_KEY) is None:
        op.bulk_insert(
            app_settings,
            [
                {
                    "key": FILM_ANALYSIS_INPUT_MODE_KEY,
                    "value": input_mode,
                    "updated_at": datetime.now(UTC).replace(tzinfo=None),
                }
            ],
        )


def downgrade() -> None:
    op.execute(app_settings.delete().where(app_settings.c.key == FILM_ANALYSIS_INPUT_MODE_KEY))
    step_models = _find_setting(AI_STEP_MODELS_KEY)
    if isinstance(step_models, dict) and AUDIO_GROUP in step_models:
        op.execute(
            app_settings.update()
            .where(app_settings.c.key == AI_STEP_MODELS_KEY)
            .values(
                value={group: model for group, model in step_models.items() if group != AUDIO_GROUP}
            )
        )
    op.execute(jobs.update().where(jobs.c.step.in_(NEW_JOB_STEPS)).values(step=None))
    op.execute(
        clone_shots.update()
        .where(clone_shots.c.frame_kind == SOUND_FRAME_KIND)
        .values(frame_kind=DIALOGUE_FRAME_KIND)
    )
    op.drop_column("prompt_preset_versions", SPEAKERS_AND_SOUNDS_COLUMN)


def _find_setting(key: str) -> object | None:
    return (
        op.get_bind()
        .execute(sa.select(app_settings.c.value).where(app_settings.c.key == key))
        .scalar_one_or_none()
    )
