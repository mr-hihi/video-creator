import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.batch.worker import BatchWorker, IdleTask, JobFinishListener, JobHandler
from app.modules.jobs.models import Job, JobStatus, JobStep, JobType
from app.modules.jobs.repository import JobRepository

JOB_ID = "job-1"
SHORT_POLL_INTERVAL_SEC = 0.01
LONG_POLL_INTERVAL_SEC = 60.0
THREAD_SETTLE_SEC = 0.1


def build_job() -> Job:
    return Job(
        id=JOB_ID,
        type=JobType.VIDEO_TO_MARKDOWN,
        status=JobStatus.PROCESSING,
        source_filename="clip.mp4",
        options={},
    )


def report_transcribing(job, report_step):
    report_step(JobStep.TRANSCRIBING)


@pytest.fixture
def repository():
    job_repository = MagicMock(spec=JobRepository)
    job_repository.claim_next_pending.return_value = build_job()
    job_repository.requeue_processing.return_value = 0
    return job_repository


@pytest.fixture
def handler():
    return MagicMock(spec=JobHandler)


@pytest.fixture
def worker(repository, handler):
    return BatchWorker(repository, {JobType.VIDEO_TO_MARKDOWN: handler}, SHORT_POLL_INTERVAL_SEC)


@pytest.fixture
def idle_run_result(repository, worker):
    repository.claim_next_pending.return_value = None
    return worker.run_once()


@pytest.fixture
def successful_run_result(handler, worker):
    handler.handle.side_effect = report_transcribing
    return worker.run_once()


@pytest.fixture
def failed_run(handler, worker):
    handler.handle.side_effect = RuntimeError("whisper crashed")
    return worker.run_once()


@pytest.fixture
def failed_run_without_message(handler, worker):
    handler.handle.side_effect = RuntimeError()
    return worker.run_once()


@pytest.fixture
def unhandled_type_run(repository):
    return BatchWorker(repository, {}, SHORT_POLL_INTERVAL_SEC).run_once()


@pytest.fixture
def interrupted_run(handler, worker):
    handler.handle.side_effect = RuntimeError("terminated")
    worker.stop()
    return worker.run_once()


@pytest.fixture
def worker_after_failing_claims(repository, worker):
    repository.claim_next_pending.side_effect = RuntimeError("database down")
    worker.start()
    time.sleep(THREAD_SETTLE_SEC)
    worker.stop()
    worker.wait_until_stopped()
    return worker


@pytest.fixture
def requeue_log_messages(repository, worker, caplog):
    repository.requeue_processing.return_value = 2
    repository.claim_next_pending.return_value = None
    with caplog.at_level("INFO", logger="app.batch.worker"):
        worker.start()
        worker.stop()
        worker.wait_until_stopped()
    return caplog.text


@pytest.fixture
def worker_after_draining_queue(repository, worker):
    repository.claim_next_pending.side_effect = [build_job(), build_job(), None, None, None]
    worker.start()
    time.sleep(THREAD_SETTLE_SEC)
    worker.stop()
    worker.wait_until_stopped()
    return worker


@pytest.fixture
def stopped_unstarted_worker(worker):
    worker.stop()
    worker.wait_until_stopped()
    return worker


@pytest.fixture
def notified_idle_worker(repository):
    repository.claim_next_pending.return_value = None
    idle_worker = BatchWorker(repository, {}, LONG_POLL_INTERVAL_SEC)
    idle_worker.start()
    time.sleep(THREAD_SETTLE_SEC)
    idle_worker.notify()
    time.sleep(THREAD_SETTLE_SEC)
    idle_worker.stop()
    idle_worker.wait_until_stopped()
    return idle_worker


def test_start_logs_how_many_jobs_were_requeued(requeue_log_messages):
    assert "Requeued 2 job(s) interrupted by the previous shutdown" in requeue_log_messages


def test_worker_processes_queued_jobs_back_to_back(repository, worker_after_draining_queue):
    assert repository.mark_done.call_count == 2


def test_wait_until_stopped_returns_when_never_started(stopped_unstarted_worker, repository):
    repository.claim_next_pending.assert_not_called()


def test_run_once_returns_false_when_queue_is_empty(idle_run_result):
    assert idle_run_result is False


def test_run_once_marks_job_done_after_handler_succeeds(repository, successful_run_result):
    assert successful_run_result is True
    repository.mark_done.assert_called_once_with(JOB_ID)


def test_run_once_records_reported_steps(repository, successful_run_result):
    repository.update_step.assert_called_once_with(JOB_ID, JobStep.TRANSCRIBING)


def test_run_once_marks_job_failed_with_error_message(repository, failed_run):
    repository.mark_failed.assert_called_once_with(JOB_ID, "whisper crashed")
    repository.mark_done.assert_not_called()


def test_run_once_uses_error_type_when_message_is_empty(repository, failed_run_without_message):
    repository.mark_failed.assert_called_once_with(JOB_ID, "RuntimeError")


def test_run_once_fails_job_without_registered_handler(repository, unhandled_type_run):
    repository.mark_failed.assert_called_once_with(
        JOB_ID, "No handler registered for job type video_to_markdown"
    )


def test_run_once_leaves_job_processing_when_interrupted_by_shutdown(repository, interrupted_run):
    repository.mark_failed.assert_not_called()
    repository.mark_done.assert_not_called()


def test_start_requeues_jobs_interrupted_by_previous_shutdown(
    repository, worker_after_failing_claims
):
    repository.requeue_processing.assert_called_once_with()


def test_worker_keeps_polling_after_a_claim_fails(repository, worker_after_failing_claims):
    assert repository.claim_next_pending.call_count >= 2


def test_notify_wakes_an_idle_worker_before_the_poll_interval(repository, notified_idle_worker):
    assert repository.claim_next_pending.call_count == 2


@pytest.fixture
def finish_listener(worker):
    listener = MagicMock(spec=JobFinishListener)
    worker.add_finish_listener(listener)
    return listener


@pytest.fixture
def listened_run(finish_listener, handler, worker):
    handler.handle.side_effect = RuntimeError("whisper crashed")
    worker.run_once()
    return finish_listener


@pytest.fixture
def broken_listener_run(finish_listener, worker):
    finish_listener.on_job_finished.side_effect = RuntimeError("listener broke")
    return worker.run_once()


@pytest.fixture
def idle_task_run(repository, worker):
    repository.claim_next_pending.return_value = None
    idle_task = MagicMock(spec=IdleTask)
    idle_task.run_next.return_value = True
    worker.add_idle_task(idle_task)
    return SimpleNamespace(result=worker.run_once(), idle_task=idle_task)


@pytest.fixture
def idle_task_beside_job(worker):
    idle_task = MagicMock(spec=IdleTask)
    worker.add_idle_task(idle_task)
    worker.run_once()
    return idle_task


def test_finished_job_is_reported_to_listeners(listened_run):
    listened_run.on_job_finished.assert_called_once_with(JOB_ID)


def test_failing_listener_does_not_stop_the_worker(broken_listener_run):
    assert broken_listener_run is True


def test_idle_task_runs_when_no_job_waits(idle_task_run):
    assert idle_task_run.result is True
    (is_stopping,) = idle_task_run.idle_task.run_next.call_args.args
    assert is_stopping() is False


def test_idle_task_waits_while_a_job_runs(idle_task_beside_job):
    idle_task_beside_job.run_next.assert_not_called()
