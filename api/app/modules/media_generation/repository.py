from collections.abc import Collection, Mapping
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.db import utc_now
from app.modules.media_generation.models import (
    OPEN_GENERATION_STATUSES,
    GenerationRequest,
    GenerationStatus,
)
from app.modules.providers.service import ProviderQueueCounts

FAILED_COUNT_WINDOW = timedelta(hours=24)


class GenerationRequestRepository:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def add(self, request: GenerationRequest) -> GenerationRequest:
        with self._session_factory.begin() as session:
            session.add(request)
        return request

    def find_by_id(self, request_id: str) -> GenerationRequest | None:
        with self._session_factory() as session:
            return session.get(GenerationRequest, request_id)

    def find_due_queued(self, now: datetime) -> list[GenerationRequest]:
        with self._session_factory() as session:
            statement = (
                select(GenerationRequest)
                .where(
                    GenerationRequest.status == GenerationStatus.QUEUED,
                    or_(
                        GenerationRequest.next_attempt_at.is_(None),
                        GenerationRequest.next_attempt_at <= now,
                    ),
                )
                .order_by(GenerationRequest.created_at)
            )
            return list(session.scalars(statement))

    def find_open_for_clone(self, clone_id: str) -> list[GenerationRequest]:
        with self._session_factory() as session:
            statement = select(GenerationRequest).where(
                GenerationRequest.clone_id == clone_id,
                GenerationRequest.status.in_(OPEN_GENERATION_STATUSES),
            )
            return list(session.scalars(statement))

    def find_clone_ids_with_open_requests(self, clone_ids: Collection[str]) -> set[str]:
        with self._session_factory() as session:
            statement = select(GenerationRequest.clone_id).where(
                GenerationRequest.clone_id.in_(clone_ids),
                GenerationRequest.status.in_(OPEN_GENERATION_STATUSES),
            )
            return {clone_id for clone_id in session.scalars(statement) if clone_id is not None}

    def find_submitted_processing(self) -> list[GenerationRequest]:
        with self._session_factory() as session:
            statement = select(GenerationRequest).where(
                GenerationRequest.status == GenerationStatus.PROCESSING,
                GenerationRequest.external_id.is_not(None),
            )
            return list(session.scalars(statement))

    def count_processing_by_provider(self) -> dict[str, int]:
        with self._session_factory() as session:
            rows = session.execute(
                select(GenerationRequest.provider, func.count())
                .where(GenerationRequest.status == GenerationStatus.PROCESSING)
                .group_by(GenerationRequest.provider)
            )
            return {provider: count for provider, count in rows}

    def count_by_provider(self) -> dict[str, ProviderQueueCounts]:
        failed_since = utc_now() - FAILED_COUNT_WINDOW
        with self._session_factory() as session:
            rows = session.execute(
                select(GenerationRequest.provider, GenerationRequest.status, func.count())
                .where(
                    or_(
                        GenerationRequest.status.in_(OPEN_GENERATION_STATUSES),
                        and_(
                            GenerationRequest.status == GenerationStatus.FAILED,
                            GenerationRequest.finished_at >= failed_since,
                        ),
                    )
                )
                .group_by(GenerationRequest.provider, GenerationRequest.status)
            )
            counts_by_provider: dict[str, dict[GenerationStatus, int]] = {}
            for provider, request_status, count in rows:
                counts_by_provider.setdefault(provider, {})[request_status] = count
        return {
            provider: ProviderQueueCounts(
                queued=counts.get(GenerationStatus.QUEUED, 0),
                processing=counts.get(GenerationStatus.PROCESSING, 0),
                failed_last_24h=counts.get(GenerationStatus.FAILED, 0),
            )
            for provider, counts in counts_by_provider.items()
        }

    def claim(self, request_id: str) -> bool:
        with self._session_factory.begin() as session:
            claimed = session.execute(
                update(GenerationRequest)
                .where(
                    GenerationRequest.id == request_id,
                    GenerationRequest.status == GenerationStatus.QUEUED,
                )
                .values(status=GenerationStatus.PROCESSING, started_at=utc_now())
            )
            return claimed.rowcount == 1

    def requeue_unsubmitted_processing(self) -> int:
        with self._session_factory.begin() as session:
            requeued = session.execute(
                update(GenerationRequest)
                .where(
                    GenerationRequest.status == GenerationStatus.PROCESSING,
                    GenerationRequest.external_id.is_(None),
                )
                .values(status=GenerationStatus.QUEUED, started_at=None)
            )
            return requeued.rowcount

    def update_fields(self, request_id: str, values: Mapping[str, Any]) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                update(GenerationRequest).where(GenerationRequest.id == request_id).values(**values)
            )

    def cancel_queued(self, request_ids: Collection[str]) -> int:
        with self._session_factory.begin() as session:
            cancelled = session.execute(
                update(GenerationRequest)
                .where(
                    GenerationRequest.id.in_(request_ids),
                    GenerationRequest.status == GenerationStatus.QUEUED,
                )
                .values(status=GenerationStatus.CANCELLED, finished_at=utc_now())
            )
            return cancelled.rowcount

    def delete_for_clone(self, clone_id: str) -> None:
        with self._session_factory.begin() as session:
            session.execute(delete(GenerationRequest).where(GenerationRequest.clone_id == clone_id))
