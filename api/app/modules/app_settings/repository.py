from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.modules.app_settings.models import AppSetting
from app.modules.providers.models import Provider, ProviderRoute


@dataclass(frozen=True)
class AiModelSettingsSave:
    setting_values: Mapping[str, Any]
    provider_ids_by_route: Mapping[str, str]
    models_by_provider_id: Mapping[str, Mapping[str, str]]


class AppSettingRepository:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def find_values(self) -> dict[str, Any]:
        with self._session_factory() as session:
            return {setting.key: setting.value for setting in session.scalars(select(AppSetting))}

    def save_values(self, values: Mapping[str, Any]) -> None:
        with self._session_factory.begin() as session:
            _merge_values(session, values)

    def save_ai_model_settings(self, save: AiModelSettingsSave) -> None:
        with self._session_factory.begin() as session:
            _merge_values(session, save.setting_values)
            for route, provider_id in save.provider_ids_by_route.items():
                session.merge(ProviderRoute(route=route, provider_id=provider_id))
            for provider_id, models in save.models_by_provider_id.items():
                session.execute(
                    update(Provider).where(Provider.id == provider_id).values(models=models)
                )


def _merge_values(session: Session, values: Mapping[str, Any]) -> None:
    for key, value in values.items():
        session.merge(AppSetting(key=key, value=value))
