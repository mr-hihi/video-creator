import logging
import threading
from collections.abc import Callable, Mapping
from typing import Protocol

from app.modules.jobs.models import Job, JobStep, JobType
from app.modules.jobs.repository import JobRepository

STOP_TIMEOUT_SEC = 10.0

logger = logging.getLogger(__name__)


class JobHandler(Protocol):
    def handle(self, job: Job, report_step: Callable[[JobStep], None]) -> None: ...


class JobFinishListener(Protocol):
    def on_job_finished(self, job_id: str) -> None: ...


class IdleTask(Protocol):
    def run_next(self, is_stopping: Callable[[], bool]) -> bool: ...


class BatchWorker:
    def __init__(
        self,
        repository: JobRepository,
        handlers_by_type: Mapping[JobType, JobHandler],
        poll_interval_sec: float,
    ):
        self._repository = repository
        self._handlers_by_type = handlers_by_type
        self._poll_interval_sec = poll_interval_sec
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._finish_listeners: list[JobFinishListener] = []
        self._idle_tasks: list[IdleTask] = []

    def add_finish_listener(self, listener: JobFinishListener) -> None:
        self._finish_listeners.append(listener)

    def add_idle_task(self, idle_task: IdleTask) -> None:
        self._idle_tasks.append(idle_task)

    def start(self) -> None:
        requeued_count = self._repository.requeue_processing()
        if requeued_count:
            logger.info("Requeued %d job(s) interrupted by the previous shutdown", requeued_count)
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_forever, name="batch-worker", daemon=True)
        self._thread.start()
        logger.info("Batch worker started (poll interval %.1fs)", self._poll_interval_sec)

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()

    def wait_until_stopped(self) -> None:
        if self._thread is not None:
            self._thread.join(STOP_TIMEOUT_SEC)
        logger.info("Batch worker stopped")

    def notify(self) -> None:
        self._wake_event.set()

    def run_once(self) -> bool:
        job = self._repository.claim_next_pending()
        if job is None:
            return any(
                idle_task.run_next(self._stop_event.is_set) for idle_task in self._idle_tasks
            )
        self._process(job)
        self._tell_finish_listeners(job)
        return True

    def _poll_forever(self) -> None:
        while not self._stop_event.is_set():
            if self._run_once_safely():
                continue
            self._wake_event.wait(self._poll_interval_sec)
            self._wake_event.clear()

    def _run_once_safely(self) -> bool:
        try:
            return self.run_once()
        except Exception:
            logger.exception("Batch worker could not claim a job; retrying after the poll interval")
            return False

    def _process(self, job: Job) -> None:
        handler = self._handlers_by_type.get(job.type)
        if handler is None:
            self._repository.mark_failed(job.id, f"No handler registered for job type {job.type}")
            logger.error("Job %s failed: no handler for type %s", job.id, job.type)
            return
        logger.info("Job %s (%s) started", job.id, job.type)
        try:
            handler.handle(job, lambda step: self._repository.update_step(job.id, step))
        except Exception as error:
            if self._stop_event.is_set():
                logger.warning("Job %s interrupted by shutdown; requeued on next start", job.id)
                return
            logger.exception("Job %s failed", job.id)
            self._repository.mark_failed(job.id, str(error) or type(error).__name__)
            return
        self._repository.mark_done(job.id)
        logger.info("Job %s done", job.id)

    def _tell_finish_listeners(self, job: Job) -> None:
        if self._stop_event.is_set():
            return
        for listener in self._finish_listeners:
            try:
                listener.on_job_finished(job.id)
            except Exception:
                logger.exception("Finish listener failed for job %s", job.id)
