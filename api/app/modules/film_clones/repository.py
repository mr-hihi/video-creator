from collections.abc import Collection, Mapping, Sequence
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.modules.ai_models.ai_calls import AiModelChoice
from app.modules.ai_models.model_choices import to_model_value
from app.modules.film_clones.models import (
    CloneAsset,
    CloneImageStatus,
    CloneScene,
    CloneShot,
    CloneStatus,
    CloneStep,
    FilmClone,
)
from app.modules.jobs.models import Job, JobOutput

LOCALIZED_FIELDS_CLEARED = {
    "changed": False,
    "localized_name": None,
    "localized_description": None,
    "localization_note": None,
    "reference_status": CloneImageStatus.NONE,
    "reference_path": None,
    "reference_error": None,
}


class FilmCloneRepository:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def add_with_job(self, job: Job, clone: FilmClone) -> FilmClone:
        with self._session_factory.begin() as session:
            session.add(job)
            session.flush()
            session.add(clone)
        return clone

    def find_by_id(self, clone_id: str) -> FilmClone | None:
        with self._session_factory() as session:
            return session.get(FilmClone, clone_id)

    def find_by_job_id(self, job_id: str) -> FilmClone | None:
        with self._session_factory() as session:
            return session.scalar(select(FilmClone).where(FilmClone.job_id == job_id))

    def find_recent(self, limit: int) -> list[FilmClone]:
        with self._session_factory() as session:
            statement = select(FilmClone).order_by(FilmClone.created_at.desc()).limit(limit)
            return list(session.scalars(statement))

    def find_jobs(self, job_ids: Collection[str]) -> dict[str, Job]:
        with self._session_factory() as session:
            jobs = session.scalars(select(Job).where(Job.id.in_(job_ids)))
            return {job.id: job for job in jobs}

    def find_oldest_running(self, steps: Collection[CloneStep]) -> FilmClone | None:
        with self._session_factory() as session:
            return session.scalar(
                select(FilmClone)
                .where(FilmClone.status == CloneStatus.RUNNING, FilmClone.step.in_(steps))
                .order_by(FilmClone.updated_at)
                .limit(1)
            )

    def find_analyzing(self) -> list[FilmClone]:
        with self._session_factory() as session:
            statement = select(FilmClone).where(
                FilmClone.status == CloneStatus.RUNNING, FilmClone.step == CloneStep.ANALYZING
            )
            return list(session.scalars(statement))

    def find_assets(self, clone_id: str) -> list[CloneAsset]:
        with self._session_factory() as session:
            statement = (
                select(CloneAsset)
                .where(CloneAsset.clone_id == clone_id)
                .order_by(CloneAsset.position)
            )
            return list(session.scalars(statement))

    def find_shots(self, clone_id: str) -> list[CloneShot]:
        with self._session_factory() as session:
            statement = (
                select(CloneShot).where(CloneShot.clone_id == clone_id).order_by(CloneShot.position)
            )
            return list(session.scalars(statement))

    def find_scenes(self, clone_id: str) -> list[CloneScene]:
        with self._session_factory() as session:
            statement = (
                select(CloneScene)
                .where(CloneScene.clone_id == clone_id)
                .order_by(CloneScene.position)
            )
            return list(session.scalars(statement))

    def find_asset(self, asset_id: str) -> CloneAsset | None:
        with self._session_factory() as session:
            return session.get(CloneAsset, asset_id)

    def find_scene(self, scene_id: str) -> CloneScene | None:
        with self._session_factory() as session:
            return session.get(CloneScene, scene_id)

    def find_shot(self, shot_id: str) -> CloneShot | None:
        with self._session_factory() as session:
            return session.get(CloneShot, shot_id)

    def update_clone(self, clone_id: str, values: Mapping[str, Any]) -> None:
        with self._session_factory.begin() as session:
            session.execute(update(FilmClone).where(FilmClone.id == clone_id).values(**values))

    def save_ai_used(self, clone_id: str, step: CloneStep, choice: AiModelChoice) -> None:
        with self._session_factory.begin() as session:
            clone = session.get(FilmClone, clone_id)
            if clone is not None:
                clone.ai_used = {**clone.ai_used, step.value: to_model_value(choice)}

    def update_clone_if_step(
        self, clone_id: str, expected_step: CloneStep, values: Mapping[str, Any]
    ) -> bool:
        with self._session_factory.begin() as session:
            updated = session.execute(
                update(FilmClone)
                .where(FilmClone.id == clone_id, FilmClone.step == expected_step)
                .values(**values)
            )
            return updated.rowcount == 1

    def update_asset(self, asset_id: str, values: Mapping[str, Any]) -> None:
        with self._session_factory.begin() as session:
            session.execute(update(CloneAsset).where(CloneAsset.id == asset_id).values(**values))

    def update_assets(self, values_by_asset_id: Mapping[str, Mapping[str, Any]]) -> None:
        with self._session_factory.begin() as session:
            for asset_id, values in values_by_asset_id.items():
                session.execute(
                    update(CloneAsset).where(CloneAsset.id == asset_id).values(**values)
                )

    def update_scene(self, scene_id: str, values: Mapping[str, Any]) -> None:
        with self._session_factory.begin() as session:
            session.execute(update(CloneScene).where(CloneScene.id == scene_id).values(**values))

    def replace_assets_and_shots(
        self, clone_id: str, assets: Sequence[CloneAsset], shots: Sequence[CloneShot]
    ) -> None:
        with self._session_factory.begin() as session:
            session.execute(delete(CloneScene).where(CloneScene.clone_id == clone_id))
            session.execute(delete(CloneShot).where(CloneShot.clone_id == clone_id))
            session.execute(delete(CloneAsset).where(CloneAsset.clone_id == clone_id))
            session.add_all(assets)
            session.add_all(shots)

    def save_assets(
        self, clone_id: str, assets: Sequence[CloneAsset], clone_values: Mapping[str, Any]
    ) -> None:
        with self._session_factory.begin() as session:
            session.execute(delete(CloneAsset).where(CloneAsset.clone_id == clone_id))
            session.add_all(assets)
            session.execute(
                update(FilmClone).where(FilmClone.id == clone_id).values(**clone_values)
            )

    def save_shot_analysis(
        self,
        clone_id: str,
        values_by_shot_id: Mapping[str, Mapping[str, Any]],
        clone_values: Mapping[str, Any],
    ) -> None:
        with self._session_factory.begin() as session:
            for shot_id, values in values_by_shot_id.items():
                session.execute(update(CloneShot).where(CloneShot.id == shot_id).values(**values))
            session.execute(
                update(FilmClone).where(FilmClone.id == clone_id).values(**clone_values)
            )

    def delete_asset(self, asset: CloneAsset) -> None:
        with self._session_factory.begin() as session:
            shots = session.scalars(select(CloneShot).where(CloneShot.clone_id == asset.clone_id))
            for shot in shots:
                if asset.id in shot.asset_ids:
                    shot.asset_ids = [
                        asset_id for asset_id in shot.asset_ids if asset_id != asset.id
                    ]
            session.execute(delete(CloneAsset).where(CloneAsset.id == asset.id))

    def save_scenes(
        self, clone_id: str, scenes: Sequence[CloneScene], clone_values: Mapping[str, Any]
    ) -> None:
        with self._session_factory.begin() as session:
            session.execute(delete(CloneScene).where(CloneScene.clone_id == clone_id))
            session.add_all(scenes)
            session.execute(
                update(FilmClone).where(FilmClone.id == clone_id).values(**clone_values)
            )

    def reset_localization(self, clone_id: str, clone_values: Mapping[str, Any]) -> None:
        with self._session_factory.begin() as session:
            session.execute(delete(CloneScene).where(CloneScene.clone_id == clone_id))
            session.execute(
                update(CloneAsset)
                .where(CloneAsset.clone_id == clone_id)
                .values(**LOCALIZED_FIELDS_CLEARED)
            )
            session.execute(
                update(FilmClone).where(FilmClone.id == clone_id).values(**clone_values)
            )

    def delete_with_job(self, clone: FilmClone) -> None:
        with self._session_factory.begin() as session:
            session.execute(delete(CloneScene).where(CloneScene.clone_id == clone.id))
            session.execute(delete(CloneShot).where(CloneShot.clone_id == clone.id))
            session.execute(delete(CloneAsset).where(CloneAsset.clone_id == clone.id))
            session.execute(delete(FilmClone).where(FilmClone.id == clone.id))
            session.execute(delete(JobOutput).where(JobOutput.job_id == clone.job_id))
            session.execute(delete(Job).where(Job.id == clone.job_id))
