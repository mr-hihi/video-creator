from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.modules.providers.models import Provider, ProviderRoute


class ProviderRepository:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def find_all(self) -> list[Provider]:
        with self._session_factory() as session:
            return list(session.scalars(select(Provider)))

    def find_by_id(self, provider_id: str) -> Provider | None:
        with self._session_factory() as session:
            return session.get(Provider, provider_id)

    def add_all(self, providers: Sequence[Provider]) -> None:
        with self._session_factory.begin() as session:
            session.add_all(providers)

    def update_fields(self, provider_id: str, values: Mapping[str, Any]) -> None:
        with self._session_factory.begin() as session:
            session.execute(update(Provider).where(Provider.id == provider_id).values(**values))

    def find_route_provider_ids(self) -> dict[str, str]:
        with self._session_factory() as session:
            return {
                route.route: route.provider_id for route in session.scalars(select(ProviderRoute))
            }
