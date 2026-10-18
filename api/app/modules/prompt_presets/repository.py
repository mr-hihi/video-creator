from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.db import utc_now
from app.modules.prompt_presets.models import PromptPreset, PromptPresetVersion


class PromptPresetRepository:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def find_all(self) -> list[PromptPreset]:
        with self._session_factory() as session:
            statement = select(PromptPreset).order_by(
                PromptPreset.is_system.desc(), PromptPreset.name
            )
            return list(session.scalars(statement))

    def find_by_id(self, preset_id: str) -> PromptPreset | None:
        with self._session_factory() as session:
            return session.get(PromptPreset, preset_id)

    def find_by_name(self, name: str) -> PromptPreset | None:
        with self._session_factory() as session:
            statement = select(PromptPreset).where(func.lower(PromptPreset.name) == name.lower())
            return session.scalars(statement).first()

    def find_default(self) -> PromptPreset | None:
        with self._session_factory() as session:
            statement = select(PromptPreset).where(PromptPreset.is_default.is_(True))
            return session.scalars(statement).first()

    def find_system(self) -> PromptPreset | None:
        with self._session_factory() as session:
            statement = select(PromptPreset).where(PromptPreset.is_system.is_(True))
            return session.scalars(statement).first()

    def find_version(self, preset_id: str, version: int) -> PromptPresetVersion | None:
        with self._session_factory() as session:
            statement = select(PromptPresetVersion).where(
                PromptPresetVersion.preset_id == preset_id, PromptPresetVersion.version == version
            )
            return session.scalars(statement).first()

    def find_versions(self, preset_id: str) -> list[PromptPresetVersion]:
        with self._session_factory() as session:
            statement = (
                select(PromptPresetVersion)
                .where(PromptPresetVersion.preset_id == preset_id)
                .order_by(PromptPresetVersion.version.desc())
            )
            return list(session.scalars(statement))

    def add_preset(self, preset: PromptPreset, first_version: PromptPresetVersion) -> PromptPreset:
        with self._session_factory.begin() as session:
            session.add(preset)
            session.flush()
            session.add(first_version)
        return preset

    def add_version(self, version: PromptPresetVersion, kept_version_count: int) -> None:
        with self._session_factory.begin() as session:
            session.add(version)
            session.execute(
                update(PromptPreset)
                .where(PromptPreset.id == version.preset_id)
                .values(current_version=version.version, updated_at=utc_now())
            )
            session.execute(
                delete(PromptPresetVersion).where(
                    PromptPresetVersion.preset_id == version.preset_id,
                    PromptPresetVersion.version <= version.version - kept_version_count,
                )
            )

    def rename(self, preset_id: str, name: str) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                update(PromptPreset)
                .where(PromptPreset.id == preset_id)
                .values(name=name, updated_at=utc_now())
            )

    def mark_default(self, preset_id: str) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                update(PromptPreset)
                .where(PromptPreset.is_default.is_(True), PromptPreset.id != preset_id)
                .values(is_default=False)
            )
            session.execute(
                update(PromptPreset).where(PromptPreset.id == preset_id).values(is_default=True)
            )

    def delete(self, preset_id: str) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                delete(PromptPresetVersion).where(PromptPresetVersion.preset_id == preset_id)
            )
            session.execute(delete(PromptPreset).where(PromptPreset.id == preset_id))
