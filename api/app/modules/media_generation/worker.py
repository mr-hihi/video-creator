import hashlib
import logging
import threading
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.common.process import CommandError
from app.db import utc_now
from app.modules.media_generation.clip_editor import ClipEditor, SegmentJoin
from app.modules.media_generation.clip_segment_folder import ClipSegmentFolder
from app.modules.media_generation.clip_segments import CLIP_SEGMENTS_DIR_NAME, ClipPlan
from app.modules.media_generation.media_task import (
    MediaResult,
    MediaTask,
    PollOutcome,
    ProviderError,
    ProviderErrorKind,
)
from app.modules.media_generation.models import GenerationKind, GenerationRequest, GenerationStatus
from app.modules.media_generation.provider_adapter import MediaProviderAdapter
from app.modules.media_generation.repository import GenerationRequestRepository
from app.modules.media_generation.retry_policy import (
    UNUSUAL_ACTIVITY_PAUSE_SEC,
    RetryAction,
    decide_retry,
)
from app.modules.media_generation.targets import GenerationTarget
from app.modules.media_generation.task_builder import (
    CLIP_LENGTH_PARAM,
    PASS_PARAM,
    PASS_RESULT_PATH_PARAM,
    PASSES_PARAM,
    PROVIDER_VOICE_ID_PARAM,
    SEGMENT_LENGTHS_PARAM,
    SEGMENT_PARAM,
    SEGMENTS_PARAM,
    BuiltTask,
    build_media_task,
    build_pass_task,
    build_segment_task,
)
from app.modules.providers.errors import ProviderNotSetUpError
from app.modules.providers.flow_extension import FlowExtensionBridge
from app.modules.providers.provider_catalog import ProviderId
from app.modules.providers.secret_box import redact_secret
from app.modules.providers.service import ProviderPacing, ProviderSettingService

FLOW_SUBMIT_GAP_SEC = 3
RESULT_POLL_EVERY_SEC = 10.0
RESULT_WAIT_LIMIT_SEC = 1800.0
POLL_AGAIN_ERROR_KINDS = frozenset({ProviderErrorKind.RETRYABLE, ProviderErrorKind.NO_ANSWER})
WORKER_POOL_SIZE = 16
STOP_TIMEOUT_SEC = 10.0
VIDEO_FILE_EXTENSION = "mp4"
JOIN_FAILED_MESSAGE = "Joining the clip segments failed: {error}"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GenerationWorkerTools:
    repository: GenerationRequestRepository
    provider_service: ProviderSettingService
    adapters_by_provider: Mapping[ProviderId, MediaProviderAdapter]
    targets_by_kind: Mapping[GenerationKind, GenerationTarget]
    flow_extension: FlowExtensionBridge
    clip_editor: ClipEditor


@dataclass(frozen=True)
class _SegmentRun:
    request: GenerationRequest
    built: BuiltTask
    plan: ClipPlan
    folder: ClipSegmentFolder


@dataclass(frozen=True)
class GenerationWorkerConfig:
    poll_interval_sec: float
    max_attempts: int


class GenerationWorker:
    def __init__(self, tools: GenerationWorkerTools, config: GenerationWorkerConfig):
        self._tools = tools
        self._config = config
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._flow_submit_lock = threading.Lock()
        self._last_submit_at_by_provider: dict[str, datetime] = {}
        self._executor: ThreadPoolExecutor | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        requeued_count = self._tools.repository.requeue_unsubmitted_processing()
        if requeued_count:
            logger.info("Requeued %d generation request(s) never submitted", requeued_count)
        self._stop_event.clear()
        self._executor = ThreadPoolExecutor(WORKER_POOL_SIZE, thread_name_prefix="generation")
        for request in self._tools.repository.find_submitted_processing():
            self._executor.submit(self.resume_polling, request.id)
        self._thread = threading.Thread(
            target=self._poll_forever, name="generation-worker", daemon=True
        )
        self._thread.start()
        logger.info("Generation worker started")

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()

    def wait_until_stopped(self) -> None:
        if self._thread is not None:
            self._thread.join(STOP_TIMEOUT_SEC)
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
        logger.info("Generation worker stopped")

    def notify(self) -> None:
        self._wake_event.set()

    def run_once(self) -> list[str]:
        now = utc_now()
        in_flight_by_provider = self._tools.repository.count_processing_by_provider()
        pacing_by_provider: dict[str, ProviderPacing] = {}
        dispatched_ids = []
        for request in self._tools.repository.find_due_queued(now):
            if request.provider not in pacing_by_provider:
                pacing_by_provider[request.provider] = self._tools.provider_service.get_pacing(
                    ProviderId(request.provider)
                )
            if not self._has_free_slot(
                request.provider, pacing_by_provider[request.provider], in_flight_by_provider, now
            ):
                continue
            target = self._tools.targets_by_kind.get(request.kind)
            if target is None or not target.is_ready(request):
                continue
            if not self._tools.repository.claim(request.id):
                continue
            in_flight_by_provider[request.provider] = (
                in_flight_by_provider.get(request.provider, 0) + 1
            )
            self._last_submit_at_by_provider[request.provider] = now
            dispatched_ids.append(request.id)
        for request_id in dispatched_ids:
            self._dispatch(request_id)
        return dispatched_ids

    def process(self, request_id: str) -> None:
        request = self._tools.repository.find_by_id(request_id)
        if request is None:
            return
        self._tools.targets_by_kind[request.kind].mark_processing(request)
        self._generate(request, None)

    def resume_polling(self, request_id: str) -> None:
        request = self._tools.repository.find_by_id(request_id)
        if request is None or request.external_id is None:
            return
        self._generate(request, request.external_id)

    def _generate(self, request: GenerationRequest, resume_external_id: str | None) -> None:
        target = self._tools.targets_by_kind[request.kind]
        api_key = None
        try:
            access = self._tools.provider_service.get_access(ProviderId(request.provider))
            api_key = access.api_key
            built = build_media_task(request, access)
            self._tools.repository.update_fields(request.id, {"params": built.sent_params})
            result = self._produce(request, target, built, resume_external_id)
            self._remember_provider_voice(request, result)
            self._finish_done(request, target, result)
        except ProviderNotSetUpError as error:
            self._finish_failed(request, target, str(error), request.attempts)
        except ProviderError as error:
            self._handle_provider_error(request, target, error, api_key)
        except Exception as error:
            if self._stop_event.is_set():
                logger.warning("Generation request %s interrupted by shutdown", request.id)
                return
            logger.exception("Generation request %s raised", request.id)
            self._handle_provider_error(
                request,
                target,
                ProviderError(str(error) or type(error).__name__, ProviderErrorKind.FATAL),
                api_key,
            )

    def _dispatch(self, request_id: str) -> None:
        if self._executor is None:
            self.process(request_id)
            return
        self._executor.submit(self.process, request_id)

    def _poll_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception:
                logger.exception("Generation worker could not claim requests")
            self._wake_event.wait(self._config.poll_interval_sec)
            self._wake_event.clear()

    def _has_free_slot(
        self,
        provider: str,
        pacing: ProviderPacing,
        in_flight_by_provider: Mapping[str, int],
        now: datetime,
    ) -> bool:
        min_interval_s = pacing.min_interval_s
        if provider == ProviderId.GOOGLE_FLOW:
            if self._tools.flow_extension.paused_until() is not None:
                return False
            min_interval_s = max(min_interval_s, FLOW_SUBMIT_GAP_SEC)
        if in_flight_by_provider.get(provider, 0) >= pacing.max_concurrent:
            return False
        last_submit_at = self._last_submit_at_by_provider.get(provider)
        return last_submit_at is None or now - last_submit_at >= timedelta(seconds=min_interval_s)

    def _produce(
        self,
        request: GenerationRequest,
        target: GenerationTarget,
        built: BuiltTask,
        resume_external_id: str | None,
    ) -> MediaResult:
        if built.pass_count > 1:
            return self._run_passes(request, target, built, resume_external_id)
        if built.clip_plan is not None and built.clip_plan.is_cut_or_joined:
            folder = ClipSegmentFolder(
                target.output_path(request, VIDEO_FILE_EXTENSION).parent / CLIP_SEGMENTS_DIR_NAME
            )
            return self._run_segments(
                _SegmentRun(request, built, built.clip_plan, folder), resume_external_id
            )
        if resume_external_id is None:
            return self._submit_and_wait(request, built.task)
        return self._wait_for_result(
            self._get_adapter(request.provider), built.task, resume_external_id
        )

    def _run_passes(
        self,
        request: GenerationRequest,
        target: GenerationTarget,
        built: BuiltTask,
        resume_external_id: str | None,
    ) -> MediaResult:
        first_pass = built.sent_params.get(PASS_PARAM, 1)
        previous_result = _to_optional_path(built.sent_params.get(PASS_RESULT_PATH_PARAM))
        params = {**built.sent_params, PASSES_PARAM: built.pass_count}
        for pass_number in range(first_pass, built.pass_count + 1):
            params = {**params, PASS_PARAM: pass_number}
            self._tools.repository.update_fields(request.id, {"params": params})
            pass_task = build_pass_task(built, pass_number, previous_result)
            if resume_external_id is None:
                result = self._submit_and_wait(request, pass_task)
            else:
                result = self._wait_for_result(
                    self._get_adapter(request.provider), pass_task, resume_external_id
                )
                resume_external_id = None
            if pass_number == built.pass_count:
                _discard(previous_result)
                return result
            pass_result = _to_pass_result_path(
                target.output_path(request, result.file_extension), pass_number
            )
            _write_result(pass_result, result.content)
            _discard(previous_result)
            previous_result = pass_result
            params = {**params, PASS_RESULT_PATH_PARAM: str(pass_result)}
            self._tools.repository.update_fields(
                request.id, {"params": params, "external_id": None}
            )
        raise ProviderError(f"Pass {first_pass} is past the last pass", ProviderErrorKind.FATAL)

    def _run_segments(self, run: _SegmentRun, resume_external_id: str | None) -> MediaResult:
        run.folder.ensure_made_from(_describe_segment_source(run.request, run.built))
        resumed_segment = run.built.sent_params.get(SEGMENT_PARAM, 1)
        for number in range(1, run.plan.segment_count + 1):
            if run.folder.has_segment(number):
                continue
            self._make_segment(
                run, number, resume_external_id if number == resumed_segment else None
            )
            resume_external_id = None
        return self._join_segments(run)

    def _make_segment(self, run: _SegmentRun, number: int, resume_external_id: str | None) -> None:
        if run.plan.segment_count > 1:
            params = {
                **self._reload(run.request).params,
                SEGMENT_PARAM: number,
                SEGMENTS_PARAM: run.plan.segment_count,
                SEGMENT_LENGTHS_PARAM: list(run.plan.segment_lengths_s),
            }
            self._tools.repository.update_fields(run.request.id, {"params": params})
        task = build_segment_task(run.built, number, self._find_segment_start_frame(run, number))
        if resume_external_id is None:
            result = self._submit_and_wait(run.request, task)
        else:
            adapter = self._get_adapter(run.request.provider)
            result = self._wait_for_result(adapter, task, resume_external_id)
        run.folder.save_segment(number, result.content)
        self._tools.repository.update_fields(run.request.id, {"external_id": None})

    def _find_segment_start_frame(self, run: _SegmentRun, number: int) -> Path | None:
        if number == 1:
            return run.built.task.inputs.start_frame
        frame_path = run.folder.last_frame_path(number - 1)
        if not frame_path.exists():
            self._edit_clip(
                lambda: self._tools.clip_editor.save_last_frame(
                    run.folder.segment_path(number - 1), frame_path
                )
            )
        return frame_path

    def _join_segments(self, run: _SegmentRun) -> MediaResult:
        join = SegmentJoin(
            segment_paths=tuple(
                run.folder.segment_path(number) for number in range(1, run.plan.segment_count + 1)
            ),
            output_path=run.folder.joined_path(),
            clip_length_s=run.plan.clip_length_s,
            has_sound=run.built.task.model.has_sound,
        )
        self._edit_clip(lambda: self._tools.clip_editor.join_segments(join))
        content = join.output_path.read_bytes()
        run.folder.delete()
        return MediaResult(content=content, file_extension=VIDEO_FILE_EXTENSION)

    def _edit_clip(self, edit: Callable[[], None]) -> None:
        try:
            edit()
        except CommandError as error:
            raise ProviderError(
                JOIN_FAILED_MESSAGE.format(error=error), ProviderErrorKind.FATAL
            ) from error

    def _remember_provider_voice(self, request: GenerationRequest, result: MediaResult) -> None:
        if result.provider_voice_id is None:
            return
        params = {**self._reload(request).params, PROVIDER_VOICE_ID_PARAM: result.provider_voice_id}
        self._tools.repository.update_fields(request.id, {"params": params})

    def _submit_and_wait(self, request: GenerationRequest, task: MediaTask) -> MediaResult:
        adapter = self._get_adapter(request.provider)
        if request.provider == ProviderId.GOOGLE_FLOW:
            with self._flow_submit_lock:
                outcome = adapter.submit(task)
        else:
            outcome = adapter.submit(task)
        if outcome.result is not None:
            return outcome.result
        if outcome.external_id is None:
            raise ProviderError(
                f"{request.provider} answered with neither a result nor an id",
                ProviderErrorKind.FATAL,
            )
        self._tools.repository.update_fields(request.id, {"external_id": outcome.external_id})
        return self._wait_for_result(adapter, task, outcome.external_id)

    def _wait_for_result(
        self, adapter: MediaProviderAdapter, task: MediaTask, external_id: str
    ) -> MediaResult:
        waited_sec = 0.0
        while waited_sec < RESULT_WAIT_LIMIT_SEC:
            outcome = self._poll_once(adapter, task, external_id)
            if outcome.is_done and outcome.result is not None:
                return outcome.result
            if self._stop_event.wait(RESULT_POLL_EVERY_SEC):
                raise RuntimeError("Generation worker stopped")
            waited_sec += RESULT_POLL_EVERY_SEC
        raise ProviderError(
            f"No answer after {int(RESULT_WAIT_LIMIT_SEC)}s", ProviderErrorKind.FATAL
        )

    def _poll_once(
        self, adapter: MediaProviderAdapter, task: MediaTask, external_id: str
    ) -> PollOutcome:
        try:
            return adapter.poll(task, external_id)
        except ProviderError as error:
            if error.kind not in POLL_AGAIN_ERROR_KINDS:
                raise
            logger.warning(
                "Generation request %s: status check failed, asking again: %s",
                task.request_id,
                error,
            )
            return PollOutcome(is_done=False)

    def _get_adapter(self, provider: str) -> MediaProviderAdapter:
        adapter = self._tools.adapters_by_provider.get(ProviderId(provider))
        if adapter is None:
            raise ProviderError(f"No adapter is installed for {provider}", ProviderErrorKind.FATAL)
        return adapter

    def _finish_done(
        self, request: GenerationRequest, target: GenerationTarget, result: MediaResult
    ) -> None:
        output_path = target.output_path(request, result.file_extension)
        _write_result(output_path, result.content)
        self._tools.repository.update_fields(
            request.id,
            {
                "status": GenerationStatus.DONE,
                "output_path": str(output_path),
                "error_message": None,
                "finished_at": utc_now(),
            },
        )
        finished = self._reload(request)
        target.save_result(finished, output_path)
        target.on_final(finished)
        logger.info("Generation request %s done", request.id)

    def _finish_failed(
        self,
        request: GenerationRequest,
        target: GenerationTarget,
        error_message: str,
        attempts: int,
    ) -> None:
        self._tools.repository.update_fields(
            request.id,
            {
                "status": GenerationStatus.FAILED,
                "error_message": error_message,
                "attempts": attempts,
                "finished_at": utc_now(),
            },
        )
        finished = self._reload(request)
        _discard(_to_optional_path(finished.params.get(PASS_RESULT_PATH_PARAM)))
        target.mark_failed(finished, error_message)
        target.on_final(finished)
        logger.info("Generation request %s failed: %s", request.id, error_message)

    def _handle_provider_error(
        self,
        request: GenerationRequest,
        target: GenerationTarget,
        error: ProviderError,
        api_key: str | None,
    ) -> None:
        error_message = redact_secret(str(error), api_key)
        decision = decide_retry(error.kind, request.attempts, self._config.max_attempts, utc_now())
        if decision.pauses_google_flow:
            self._tools.flow_extension.pause_for(UNUSUAL_ACTIVITY_PAUSE_SEC)
        if decision.action is RetryAction.FAIL:
            self._finish_failed(request, target, error_message, decision.attempts)
            return
        self._tools.repository.update_fields(
            request.id,
            {
                "status": GenerationStatus.QUEUED,
                "attempts": decision.attempts,
                "next_attempt_at": decision.next_attempt_at,
                "external_id": None,
                "started_at": None,
                "error_message": error_message,
            },
        )
        target.mark_queued(self._reload(request))
        logger.info("Generation request %s requeued: %s", request.id, error_message)

    def _reload(self, request: GenerationRequest) -> GenerationRequest:
        return self._tools.repository.find_by_id(request.id) or request


def _write_result(output_path: Path, content: bytes) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(content)


def _to_pass_result_path(output_path: Path, pass_number: int) -> Path:
    return output_path.with_name(f"{output_path.stem}.pass{pass_number}{output_path.suffix}")


def _to_optional_path(value: str | None) -> Path | None:
    return None if value is None else Path(value)


def _describe_segment_source(request: GenerationRequest, built: BuiltTask) -> dict[str, Any]:
    start_frame = built.task.inputs.start_frame
    start_frame_digest = (
        hashlib.sha256(start_frame.read_bytes()).hexdigest()
        if start_frame is not None and start_frame.exists()
        else None
    )
    return {
        "startFrame": start_frame_digest,
        "prompt": request.prompt,
        CLIP_LENGTH_PARAM: request.params.get(CLIP_LENGTH_PARAM),
        "provider": request.provider,
        "model": built.task.model.id,
    }


def _discard(path: Path | None) -> None:
    if path is not None:
        path.unlink(missing_ok=True)
