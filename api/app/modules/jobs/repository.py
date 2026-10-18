from collections.abc import Collection, Sequence
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.db import utc_now
from app.modules.ai_models.ai_calls import AiModelChoice
from app.modules.ai_models.model_choices import to_model_value
from app.modules.jobs.models import Job, JobOutput, JobOutputKind, JobStatus, JobStep, JobType


class JobRepository:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def add(self, job: Job, outputs: Sequence[JobOutput] = ()) -> Job:
        with self._session_factory.begin() as session:
            session.add(job)
            session.flush()
            session.add_all(outputs)
        return job

    def find_by_id(self, job_id: str) -> Job | None:
        with self._session_factory() as session:
            return session.get(Job, job_id)

    def find_recent(self, limit: int, types: Collection[JobType]) -> list[Job]:
        with self._session_factory() as session:
            statement = select(Job).order_by(Job.created_at.desc()).limit(limit)
            if types:
                statement = statement.where(Job.type.in_(types))
            return list(session.scalars(statement))

    def find_outputs(self, job_id: str) -> dict[JobOutputKind, str]:
        with self._session_factory() as session:
            outputs = session.scalars(select(JobOutput).where(JobOutput.job_id == job_id))
            return {output.kind: output.content for output in outputs}

    def claim_next_pending(self) -> Job | None:
        with self._session_factory.begin() as session:
            oldest_pending_id = session.scalar(
                select(Job.id)
                .where(Job.status == JobStatus.PENDING)
                .order_by(Job.created_at)
                .limit(1)
            )
            if oldest_pending_id is None:
                return None
            claimed = session.execute(
                update(Job)
                .where(Job.id == oldest_pending_id, Job.status == JobStatus.PENDING)
                .values(status=JobStatus.PROCESSING, step=None, started_at=utc_now())
            )
            if claimed.rowcount != 1:
                return None
            return session.get(Job, oldest_pending_id)

    def requeue_processing(self) -> int:
        with self._session_factory.begin() as session:
            requeued = session.execute(
                update(Job)
                .where(Job.status == JobStatus.PROCESSING)
                .values(status=JobStatus.PENDING, step=None, started_at=None)
            )
            return requeued.rowcount

    def update_step(self, job_id: str, step: JobStep) -> None:
        self._update(job_id, step=step)

    def merge_options(self, job_id: str, extra_options: dict[str, Any]) -> None:
        with self._session_factory.begin() as session:
            job = session.get(Job, job_id)
            if job is not None:
                job.options = {**job.options, **extra_options}

    def save_ai_used(self, job_id: str, step: JobStep, choice: AiModelChoice) -> None:
        with self._session_factory.begin() as session:
            job = session.get(Job, job_id)
            if job is not None:
                job.ai_used = {**job.ai_used, step.value: to_model_value(choice)}

    def save_output(self, job_id: str, kind: JobOutputKind, content: str) -> None:
        with self._session_factory.begin() as session:
            session.merge(JobOutput(job_id=job_id, kind=kind, content=content))

    def delete_outputs(self, job_id: str, kinds: Collection[JobOutputKind]) -> None:
        with self._session_factory.begin() as session:
            session.execute(
                delete(JobOutput).where(JobOutput.job_id == job_id, JobOutput.kind.in_(kinds))
            )

    def delete(self, job_id: str) -> None:
        with self._session_factory.begin() as session:
            session.execute(delete(JobOutput).where(JobOutput.job_id == job_id))
            session.execute(delete(Job).where(Job.id == job_id))

    def mark_done(self, job_id: str) -> None:
        self._update(job_id, status=JobStatus.DONE, step=None, finished_at=utc_now())

    def mark_failed(self, job_id: str, error_message: str) -> None:
        self._update(
            job_id, status=JobStatus.FAILED, error_message=error_message, finished_at=utc_now()
        )

    def _update(self, job_id: str, **values) -> None:
        with self._session_factory.begin() as session:
            session.execute(update(Job).where(Job.id == job_id).values(**values))
