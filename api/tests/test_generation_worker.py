from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.common.process import CommandError
from app.modules.media_generation.clip_editor import SegmentJoin
from app.modules.media_generation.media_task import (
    MediaResult,
    MediaTask,
    PollOutcome,
    ProviderError,
    ProviderErrorKind,
    SubmitOutcome,
)
from app.modules.media_generation.models import GenerationKind, GenerationRequest, GenerationStatus
from app.modules.media_generation.repository import GenerationRequestRepository
from app.modules.media_generation.worker import (
    GenerationWorker,
    GenerationWorkerConfig,
    GenerationWorkerTools,
)
from app.modules.providers.errors import ProviderNotSetUpError
from app.modules.providers.flow_extension import FlowExtensionBridge
from app.modules.providers.model_catalog import CatalogModel
from app.modules.providers.provider_catalog import MediaKind, ProviderId
from app.modules.providers.service import ProviderAccess, ProviderPacing, ProviderSettingService

API_KEY = "sk-secret-1234"
OPENAI_IMAGE = CatalogModel("gpt-image-2.5-sunburst", "GPT Image 2.5", max_references=2)
EIGHT_SECOND_VIDEO = CatalogModel("veo-3.1-fast", "Veo 3.1 Fast", clip_lengths_s=(8,))
CREATED_AT = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
PASS_PROMPT_START = "Keep the scene, the framing and everyone else unchanged."
DEFAULT_PACING = ProviderPacing(max_concurrent=2, min_interval_s=0)


class InMemoryRequests:
    def __init__(self, requests: list[GenerationRequest]):
        self.requests_by_id = {request.id: request for request in requests}

    def find_by_id(self, request_id: str) -> GenerationRequest | None:
        return self.requests_by_id.get(request_id)

    def find_due_queued(self, now: datetime) -> list[GenerationRequest]:
        return [
            request
            for request in self.requests_by_id.values()
            if request.status is GenerationStatus.QUEUED
            and (request.next_attempt_at is None or request.next_attempt_at <= now)
        ]

    def count_processing_by_provider(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for request in self.requests_by_id.values():
            if request.status is GenerationStatus.PROCESSING:
                counts[request.provider] = counts.get(request.provider, 0) + 1
        return counts

    def claim(self, request_id: str) -> bool:
        request = self.requests_by_id[request_id]
        if request.status is not GenerationStatus.QUEUED:
            return False
        request.status = GenerationStatus.PROCESSING
        return True

    def update_fields(self, request_id: str, values: Mapping[str, Any]) -> None:
        for name, value in values.items():
            setattr(self.requests_by_id[request_id], name, value)


@dataclass
class ScriptedAdapter:
    answers: list[Any]
    submitted_tasks: list[MediaTask] = field(default_factory=list)
    polled_ids: list[str] = field(default_factory=list)

    def submit(self, task: MediaTask) -> SubmitOutcome:
        self.submitted_tasks.append(task)
        return self._next_answer()

    def poll(self, task: MediaTask, external_id: str) -> PollOutcome:
        self.polled_ids.append(external_id)
        return PollOutcome(is_done=True, result=self._next_answer().result)

    def _next_answer(self) -> SubmitOutcome:
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, SubmitOutcome):
            return answer
        if isinstance(answer, MediaResult):
            return SubmitOutcome(result=answer)
        return SubmitOutcome(result=MediaResult(content=answer, file_extension="png"))


@dataclass
class RecordingTarget:
    output_dir: Path
    is_ready_answer: bool = True
    saved_paths: list[Path] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    queued_ids: list[str] = field(default_factory=list)
    final_statuses: list[GenerationStatus] = field(default_factory=list)

    def mark_queued(self, request: GenerationRequest) -> None:
        self.queued_ids.append(request.id)

    def is_ready(self, request: GenerationRequest) -> bool:
        return self.is_ready_answer

    def mark_processing(self, request: GenerationRequest) -> None:
        return None

    def output_path(self, request: GenerationRequest, file_extension: str) -> Path:
        return self.output_dir / request.id / f"image.{file_extension}"

    def save_result(self, request: GenerationRequest, file_path: Path) -> None:
        self.saved_paths.append(file_path)

    def mark_failed(self, request: GenerationRequest, error_message: str) -> None:
        self.failures.append(error_message)

    def mark_cancelled(self, request: GenerationRequest) -> None:
        return None

    def on_final(self, request: GenerationRequest) -> None:
        self.final_statuses.append(request.status)


@dataclass
class RecordingClipEditor:
    join_error: Exception | None = None
    frame_sources: list[Path] = field(default_factory=list)
    joins: list[SegmentJoin] = field(default_factory=list)

    def save_last_frame(self, clip_path: Path, frame_path: Path) -> None:
        self.frame_sources.append(clip_path)
        frame_path.write_bytes(b"last-frame")

    def join_segments(self, join: SegmentJoin) -> None:
        self.joins.append(join)
        if self.join_error is not None:
            raise self.join_error
        join.output_path.write_bytes(b"+".join(path.read_bytes() for path in join.segment_paths))


@dataclass
class WorkerRig:
    worker: GenerationWorker
    requests: InMemoryRequests
    adapter: ScriptedAdapter
    target: RecordingTarget
    flow_extension: FlowExtensionBridge
    clip_editor: RecordingClipEditor


def build_request(**overrides) -> GenerationRequest:
    fields = {
        "id": "request-1",
        "kind": GenerationKind.CLONE_SCENE_IMAGE,
        "media_kind": MediaKind.IMAGE,
        "provider": ProviderId.OPENAI.value,
        "prompt": "A pier at dawn",
        "input_paths": {},
        "params": {},
        "status": GenerationStatus.QUEUED,
        "attempts": 0,
        "external_id": None,
        "next_attempt_at": None,
        "created_at": CREATED_AT,
    }
    return GenerationRequest(**{**fields, **overrides})


def build_rig(
    tmp_path: Path,
    requests: list[GenerationRequest],
    answers: list[Any],
    access_error: Exception | None = None,
    pacing: ProviderPacing = DEFAULT_PACING,
    is_ready: bool = True,
) -> WorkerRig:
    in_memory = InMemoryRequests(requests)
    provider_service = MagicMock(spec=ProviderSettingService)
    provider_service.get_pacing.return_value = pacing
    provider_service.get_access.side_effect = access_error
    provider_service.get_access.return_value = ProviderAccess(
        provider_id=ProviderId.OPENAI,
        name="OpenAI",
        api_key=API_KEY,
        base_url=None,
        models={MediaKind.IMAGE: OPENAI_IMAGE, MediaKind.VIDEO: EIGHT_SECOND_VIDEO},
        flow_project_id=None,
    )
    adapter = ScriptedAdapter(answers=list(answers))
    target = RecordingTarget(output_dir=tmp_path, is_ready_answer=is_ready)
    flow_extension = FlowExtensionBridge()
    clip_editor = RecordingClipEditor()
    worker = GenerationWorker(
        GenerationWorkerTools(
            repository=MagicMock(spec=GenerationRequestRepository, wraps=in_memory),
            provider_service=provider_service,
            adapters_by_provider={ProviderId.OPENAI: adapter, ProviderId.GOOGLE_FLOW: adapter},
            targets_by_kind={
                GenerationKind.CLONE_SCENE_IMAGE: target,
                GenerationKind.SCENE_CLIP: target,
            },
            flow_extension=flow_extension,
            clip_editor=clip_editor,
        ),
        GenerationWorkerConfig(poll_interval_sec=5.0, max_attempts=5),
    )
    return WorkerRig(worker, in_memory, adapter, target, flow_extension, clip_editor)


def three_reference_request(**overrides) -> GenerationRequest:
    return build_request(
        input_paths={"references": ["a.png", "b.png", "c.png"]},
        params={"referenceNames": ["Ann", "Bao", "Chi"]},
        **overrides,
    )


@pytest.fixture
def finished_rig(tmp_path):
    rig = build_rig(tmp_path, [build_request()], [b"image-bytes"])
    rig.worker.run_once()
    return rig


@pytest.fixture
def async_rig(tmp_path):
    rig = build_rig(tmp_path, [build_request()], [SubmitOutcome(external_id="op-1"), b"late"])
    rig.worker.run_once()
    return rig


@pytest.fixture
def busy_rig(tmp_path):
    rig = build_rig(
        tmp_path,
        [
            build_request(id="running", status=GenerationStatus.PROCESSING),
            build_request(id="waiting"),
        ],
        [],
        pacing=ProviderPacing(max_concurrent=1, min_interval_s=0),
    )
    rig.worker.run_once()
    return rig


@pytest.fixture
def spaced_rig(tmp_path):
    rig = build_rig(
        tmp_path,
        [build_request(id="first"), build_request(id="second")],
        [b"first-image"],
        pacing=ProviderPacing(max_concurrent=2, min_interval_s=5),
    )
    rig.worker.run_once()
    return rig


@pytest.fixture
def flow_gap_rig(tmp_path):
    rig = build_rig(
        tmp_path,
        [
            build_request(id="first", provider=ProviderId.GOOGLE_FLOW.value),
            build_request(id="second", provider=ProviderId.GOOGLE_FLOW.value),
        ],
        [b"first-image"],
        pacing=ProviderPacing(max_concurrent=10, min_interval_s=0),
    )
    rig.worker.run_once()
    return rig


@pytest.fixture
def not_ready_rig(tmp_path):
    rig = build_rig(tmp_path, [build_request()], [], is_ready=False)
    rig.worker.run_once()
    return rig


@pytest.fixture
def no_target_rig(tmp_path):
    rig = build_rig(tmp_path, [build_request(kind=GenerationKind.SCENE_IMAGE)], [])
    rig.worker.run_once()
    return rig


@pytest.fixture
def paused_flow_rig(tmp_path):
    rig = build_rig(tmp_path, [build_request(provider=ProviderId.GOOGLE_FLOW.value)], [])
    rig.flow_extension.pause_for(120)
    rig.worker.run_once()
    return rig


@pytest.fixture
def multi_pass_rig(tmp_path):
    rig = build_rig(tmp_path, [three_reference_request()], [b"pass-1", b"pass-2", b"pass-3"])
    rig.worker.run_once()
    return rig


@pytest.fixture
def failed_pass_rig(tmp_path):
    rig = build_rig(
        tmp_path,
        [three_reference_request()],
        [
            b"pass-1",
            b"pass-2",
            ProviderError("Internal error", ProviderErrorKind.RETRYABLE),
            b"pass-3-retry",
        ],
    )
    rig.worker.run_once()
    return rig


@pytest.fixture
def retried_pass_rig(failed_pass_rig):
    failed_pass_rig.requests.update_fields("request-1", {"next_attempt_at": None})
    failed_pass_rig.adapter.submitted_tasks.clear()
    failed_pass_rig.worker.run_once()
    return failed_pass_rig


@pytest.fixture
def resumed_rig(tmp_path):
    rig = build_rig(
        tmp_path,
        [build_request(status=GenerationStatus.PROCESSING, external_id="op-7")],
        [b"resumed"],
    )
    rig.worker.resume_polling("request-1")
    return rig


@pytest.fixture
def resumed_pass_rig(tmp_path):
    pass_one_result = tmp_path / "request-1" / "image.pass1.png"
    pass_one_result.parent.mkdir(parents=True)
    pass_one_result.write_bytes(b"pass-1")
    rig = build_rig(
        tmp_path,
        [
            build_request(
                status=GenerationStatus.PROCESSING,
                external_id="op-pass-2",
                input_paths={"references": ["a.png", "b.png", "c.png"]},
                params={"pass": 2, "passes": 3, "passResultPath": str(pass_one_result)},
            )
        ],
        [b"pass-2", b"pass-3"],
    )
    rig.worker.resume_polling("request-1")
    return rig


@pytest.fixture
def not_set_up_rig(tmp_path):
    rig = build_rig(tmp_path, [build_request()], [], access_error=ProviderNotSetUpError("OpenAI"))
    rig.worker.run_once()
    return rig


@pytest.fixture
def fatal_rig(tmp_path):
    rig = build_rig(
        tmp_path,
        [build_request()],
        [ProviderError(f"OpenAI: invalid key {API_KEY}", ProviderErrorKind.FATAL)],
    )
    rig.worker.run_once()
    return rig


@pytest.fixture
def unusual_activity_rig(tmp_path):
    rig = build_rig(
        tmp_path,
        [build_request()],
        [ProviderError("unusual activity", ProviderErrorKind.UNUSUAL_ACTIVITY)],
    )
    rig.worker.run_once()
    return rig


@pytest.fixture
def voice_copy_rig(tmp_path):
    rig = build_rig(
        tmp_path,
        [build_request()],
        [MediaResult(content=b"audio", file_extension="mp3", provider_voice_id="el-voice-1")],
    )
    rig.worker.run_once()
    return rig


@pytest.fixture
def timed_out_submit_rig(tmp_path):
    rig = build_rig(
        tmp_path,
        [build_request()],
        [ProviderError("OpenAI timed out: timed out", ProviderErrorKind.NO_ANSWER)],
    )
    rig.worker.run_once()
    return rig


@pytest.fixture
def short_poll_wait(monkeypatch):
    monkeypatch.setattr("app.modules.media_generation.worker.RESULT_POLL_EVERY_SEC", 0.001)


@pytest.fixture
def poll_hiccup_rig(tmp_path, short_poll_wait):
    rig = build_rig(
        tmp_path,
        [build_request()],
        [
            SubmitOutcome(external_id="op-1"),
            ProviderError("OpenAI timed out: timed out", ProviderErrorKind.NO_ANSWER),
            ProviderError("OpenAI: HTTP 503", ProviderErrorKind.RETRYABLE),
            b"late",
        ],
    )
    rig.worker.run_once()
    return rig


@pytest.fixture
def poll_refused_rig(tmp_path, short_poll_wait):
    rig = build_rig(
        tmp_path,
        [build_request()],
        [
            SubmitOutcome(external_id="op-1"),
            ProviderError("Replicate: GPU lost", ProviderErrorKind.FATAL),
        ],
    )
    rig.worker.run_once()
    return rig


@pytest.fixture
def poll_without_result_rig(tmp_path, monkeypatch):
    monkeypatch.setattr("app.modules.media_generation.worker.RESULT_WAIT_LIMIT_SEC", 0.0)
    rig = build_rig(tmp_path, [build_request()], [SubmitOutcome(external_id="op-1")])
    rig.worker.run_once()
    return rig


@pytest.fixture
def crashed_rig(tmp_path):
    rig = build_rig(tmp_path, [build_request()], [RuntimeError("socket closed")])
    rig.worker.run_once()
    return rig


def build_clip_request(tmp_path: Path, params: dict[str, Any], **overrides) -> GenerationRequest:
    start_image = tmp_path / "scene.png"
    start_image.write_bytes(b"scene-image")
    return build_request(
        kind=GenerationKind.SCENE_CLIP,
        media_kind=MediaKind.VIDEO,
        input_paths={"startFrame": str(start_image)},
        params=params,
        **overrides,
    )


def segment_dir(tmp_path: Path) -> Path:
    return tmp_path / "request-1" / "clip-segments"


@pytest.fixture
def joined_clip_rig(tmp_path):
    rig = build_rig(
        tmp_path, [build_clip_request(tmp_path, {"clipLengthS": 15})], [b"seg-1", b"seg-2"]
    )
    rig.worker.run_once()
    return rig


@pytest.fixture
def cut_clip_rig(tmp_path):
    rig = build_rig(tmp_path, [build_clip_request(tmp_path, {"clipLengthS": 6})], [b"clip"])
    rig.worker.run_once()
    return rig


@pytest.fixture
def failed_segment_rig(tmp_path):
    rig = build_rig(
        tmp_path,
        [build_clip_request(tmp_path, {"clipLengthS": 15})],
        [
            b"seg-1",
            ProviderError("Internal error", ProviderErrorKind.RETRYABLE),
            b"seg-2-retry",
            b"seg-2-extra",
        ],
    )
    rig.worker.run_once()
    return rig


@pytest.fixture
def retried_segment_rig(failed_segment_rig):
    failed_segment_rig.requests.update_fields("request-1", {"next_attempt_at": None})
    failed_segment_rig.adapter.submitted_tasks.clear()
    failed_segment_rig.worker.run_once()
    return failed_segment_rig


@pytest.fixture
def resumed_segment_rig(failed_segment_rig):
    failed_segment_rig.requests.update_fields(
        "request-1", {"status": GenerationStatus.PROCESSING, "external_id": "op-seg-2"}
    )
    failed_segment_rig.adapter.submitted_tasks.clear()
    failed_segment_rig.worker.resume_polling("request-1")
    return failed_segment_rig


@pytest.fixture
def changed_prompt_rig(failed_segment_rig):
    failed_segment_rig.requests.update_fields(
        "request-1", {"prompt": "A pier at dusk", "next_attempt_at": None}
    )
    failed_segment_rig.adapter.submitted_tasks.clear()
    failed_segment_rig.worker.run_once()
    return failed_segment_rig


@pytest.fixture
def failed_join_rig(tmp_path):
    rig = build_rig(
        tmp_path, [build_clip_request(tmp_path, {"clipLengthS": 15})], [b"seg-1", b"seg-2"]
    )
    rig.clip_editor.join_error = CommandError("ffmpeg exited 1: bad stream")
    rig.worker.run_once()
    return rig


def test_run_once_saves_the_result_to_the_target_file(finished_rig, tmp_path):
    request = finished_rig.requests.find_by_id("request-1")
    output_path = tmp_path / "request-1" / "image.png"
    assert request.status is GenerationStatus.DONE
    assert request.output_path == str(output_path)
    assert request.params == {"model": "gpt-image-2.5-sunburst"}
    assert output_path.read_bytes() == b"image-bytes"
    assert finished_rig.target.saved_paths == [output_path]
    assert finished_rig.target.final_statuses == [GenerationStatus.DONE]


def test_submitted_request_stores_the_external_id_and_polls_it(async_rig):
    request = async_rig.requests.find_by_id("request-1")
    assert request.external_id == "op-1"
    assert async_rig.adapter.polled_ids == ["op-1"]
    assert request.status is GenerationStatus.DONE


def test_provider_without_a_free_slot_leaves_the_request_queued(busy_rig):
    assert busy_rig.requests.find_by_id("waiting").status is GenerationStatus.QUEUED
    assert busy_rig.adapter.submitted_tasks == []


def test_min_interval_holds_the_next_request_although_a_slot_is_free(spaced_rig):
    assert spaced_rig.requests.find_by_id("first").status is GenerationStatus.DONE
    assert spaced_rig.requests.find_by_id("second").status is GenerationStatus.QUEUED
    assert len(spaced_rig.adapter.submitted_tasks) == 1


def test_google_flow_submits_one_at_a_time_with_no_interval_set(flow_gap_rig):
    assert flow_gap_rig.requests.find_by_id("second").status is GenerationStatus.QUEUED
    assert len(flow_gap_rig.adapter.submitted_tasks) == 1


def test_request_whose_dependency_is_missing_stays_queued(not_ready_rig):
    assert not_ready_rig.requests.find_by_id("request-1").status is GenerationStatus.QUEUED


def test_request_of_a_kind_without_a_target_stays_queued(no_target_rig):
    assert no_target_rig.requests.find_by_id("request-1").status is GenerationStatus.QUEUED


def test_paused_google_flow_claims_nothing(paused_flow_rig):
    assert paused_flow_rig.requests.find_by_id("request-1").status is GenerationStatus.QUEUED


def test_more_references_than_the_model_takes_run_in_passes(multi_pass_rig, tmp_path):
    first, second, third = multi_pass_rig.adapter.submitted_tasks
    request = multi_pass_rig.requests.find_by_id("request-1")
    assert [path.name for path in first.inputs.references] == ["a.png"]
    assert first.inputs.source_image is None
    assert first.prompt == "A pier at dawn"
    assert [path.name for path in second.inputs.references] == ["b.png"]
    assert second.inputs.source_image == tmp_path / "request-1" / "image.pass1.png"
    assert second.prompt.startswith(PASS_PROMPT_START)
    assert "Make Bao look like" in second.prompt
    assert third.inputs.source_image == tmp_path / "request-1" / "image.pass2.png"
    assert "Make Chi look like" in third.prompt
    assert request.params["pass"] == 3
    assert request.params["passes"] == 3
    assert (tmp_path / "request-1" / "image.png").read_bytes() == b"pass-3"
    assert sorted(path.name for path in (tmp_path / "request-1").iterdir()) == ["image.png"]


def test_failing_pass_requeues_at_that_pass_with_the_previous_result(failed_pass_rig, tmp_path):
    request = failed_pass_rig.requests.find_by_id("request-1")
    pass_two_result = tmp_path / "request-1" / "image.pass2.png"
    assert request.status is GenerationStatus.QUEUED
    assert request.attempts == 1
    assert request.params["pass"] == 3
    assert request.params["passResultPath"] == str(pass_two_result)
    assert pass_two_result.read_bytes() == b"pass-2"


def test_retry_starts_again_at_the_failing_pass(retried_pass_rig, tmp_path):
    (retried_task,) = retried_pass_rig.adapter.submitted_tasks
    assert [path.name for path in retried_task.inputs.references] == ["c.png"]
    assert retried_task.inputs.source_image == tmp_path / "request-1" / "image.pass2.png"
    assert (tmp_path / "request-1" / "image.png").read_bytes() == b"pass-3-retry"
    assert retried_pass_rig.requests.find_by_id("request-1").status is GenerationStatus.DONE


def test_resume_polls_the_stored_id_and_never_submits_again(resumed_rig):
    assert resumed_rig.adapter.polled_ids == ["op-7"]
    assert resumed_rig.adapter.submitted_tasks == []
    assert resumed_rig.requests.find_by_id("request-1").status is GenerationStatus.DONE


def test_resume_mid_pass_finishes_that_pass_then_runs_the_rest(resumed_pass_rig, tmp_path):
    (third_pass_task,) = resumed_pass_rig.adapter.submitted_tasks
    assert resumed_pass_rig.adapter.polled_ids == ["op-pass-2"]
    assert [path.name for path in third_pass_task.inputs.references] == ["c.png"]
    assert third_pass_task.inputs.source_image == tmp_path / "request-1" / "image.pass2.png"
    assert (tmp_path / "request-1" / "image.png").read_bytes() == b"pass-3"


def test_provider_not_set_up_fails_at_once_without_counting(not_set_up_rig):
    request = not_set_up_rig.requests.find_by_id("request-1")
    assert request.status is GenerationStatus.FAILED
    assert request.attempts == 0
    assert request.error_message == "OpenAI is not set up — open Settings"
    assert not_set_up_rig.adapter.submitted_tasks == []
    assert not_set_up_rig.target.failures == ["OpenAI is not set up — open Settings"]


def test_fatal_error_fails_at_once_without_the_api_key(fatal_rig):
    request = fatal_rig.requests.find_by_id("request-1")
    assert request.status is GenerationStatus.FAILED
    assert request.attempts == 1
    assert API_KEY not in request.error_message
    assert fatal_rig.target.final_statuses == [GenerationStatus.FAILED]


def test_unusual_activity_pauses_google_flow(unusual_activity_rig):
    assert unusual_activity_rig.requests.find_by_id("request-1").status is GenerationStatus.FAILED
    assert unusual_activity_rig.flow_extension.paused_until() is not None


def test_unexpected_exception_fails_at_once(crashed_rig):
    request = crashed_rig.requests.find_by_id("request-1")
    assert request.status is GenerationStatus.FAILED
    assert request.attempts == 1
    assert request.error_message == "socket closed"
    assert crashed_rig.target.queued_ids == []


def test_submit_without_an_answer_fails_without_submitting_again(timed_out_submit_rig):
    request = timed_out_submit_rig.requests.find_by_id("request-1")
    assert request.status is GenerationStatus.FAILED
    assert request.attempts == 1
    assert request.error_message == "OpenAI timed out: timed out"
    assert len(timed_out_submit_rig.adapter.submitted_tasks) == 1
    assert timed_out_submit_rig.target.queued_ids == []


def test_status_check_without_an_answer_is_asked_again(poll_hiccup_rig):
    request = poll_hiccup_rig.requests.find_by_id("request-1")
    assert request.status is GenerationStatus.DONE
    assert request.attempts == 0
    assert poll_hiccup_rig.adapter.polled_ids == ["op-1", "op-1", "op-1"]
    assert len(poll_hiccup_rig.adapter.submitted_tasks) == 1


def test_failure_reported_while_polling_fails_at_once(poll_refused_rig):
    request = poll_refused_rig.requests.find_by_id("request-1")
    assert request.status is GenerationStatus.FAILED
    assert request.error_message == "Replicate: GPU lost"
    assert len(poll_refused_rig.adapter.submitted_tasks) == 1


def test_no_result_within_the_wait_limit_fails(poll_without_result_rig):
    request = poll_without_result_rig.requests.find_by_id("request-1")
    assert request.status is GenerationStatus.FAILED
    assert request.error_message == "No answer after 0s"


def test_voice_copy_made_by_the_provider_is_kept_on_the_request(voice_copy_rig):
    request = voice_copy_rig.requests.find_by_id("request-1")
    assert request.params["providerVoiceId"] == "el-voice-1"
    assert request.status is GenerationStatus.DONE


def test_a_long_scene_is_made_as_segments_each_from_the_last_frame(joined_clip_rig, tmp_path):
    first_task, second_task = joined_clip_rig.adapter.submitted_tasks
    assert first_task.prompt == "Part 1 of 2. Show 0-8s of this shot.\nA pier at dawn"
    assert second_task.prompt == (
        "Part 2 of 2. Show 8-15s of this shot. Continue from the start image.\nA pier at dawn"
    )
    assert [first_task.clip_length_s, second_task.clip_length_s] == [8, 8]
    assert first_task.inputs.start_frame == tmp_path / "scene.png"
    assert second_task.inputs.start_frame == segment_dir(tmp_path) / "1-last.png"
    assert joined_clip_rig.clip_editor.frame_sources == [segment_dir(tmp_path) / "1.mp4"]


def test_the_joined_segments_are_cut_to_the_scene_length_and_saved(joined_clip_rig, tmp_path):
    (join,) = joined_clip_rig.clip_editor.joins
    request = joined_clip_rig.requests.find_by_id("request-1")
    assert join.segment_paths == (segment_dir(tmp_path) / "1.mp4", segment_dir(tmp_path) / "2.mp4")
    assert (join.clip_length_s, join.has_sound) == (15, True)
    assert (tmp_path / "request-1" / "image.mp4").read_bytes() == b"seg-1+seg-2"
    assert request.status is GenerationStatus.DONE
    assert (request.params["segment"], request.params["segments"]) == (2, 2)
    assert request.params["segmentLengths"] == [8, 8]
    assert not segment_dir(tmp_path).exists()


def test_a_scene_shorter_than_the_clip_is_cut_from_one_clip(cut_clip_rig, tmp_path):
    (task,) = cut_clip_rig.adapter.submitted_tasks
    (join,) = cut_clip_rig.clip_editor.joins
    request = cut_clip_rig.requests.find_by_id("request-1")
    assert (task.prompt, task.clip_length_s) == ("A pier at dawn", 8)
    assert (join.segment_paths, join.clip_length_s) == ((segment_dir(tmp_path) / "1.mp4",), 6)
    assert "segment" not in request.params
    assert (tmp_path / "request-1" / "image.mp4").read_bytes() == b"clip"


def test_a_failing_segment_requeues_and_keeps_the_done_ones(failed_segment_rig, tmp_path):
    request = failed_segment_rig.requests.find_by_id("request-1")
    assert request.status is GenerationStatus.QUEUED
    assert request.params["segment"] == 2
    assert (segment_dir(tmp_path) / "1.mp4").read_bytes() == b"seg-1"


def test_a_retry_makes_only_the_missing_segments(retried_segment_rig, tmp_path):
    (retried_task,) = retried_segment_rig.adapter.submitted_tasks
    assert retried_task.prompt.startswith("Part 2 of 2.")
    assert (tmp_path / "request-1" / "image.mp4").read_bytes() == b"seg-1+seg-2-retry"


def test_a_resume_polls_the_segment_it_was_waiting_for(resumed_segment_rig, tmp_path):
    assert resumed_segment_rig.adapter.polled_ids == ["op-seg-2"]
    assert resumed_segment_rig.adapter.submitted_tasks == []
    assert (tmp_path / "request-1" / "image.mp4").read_bytes() == b"seg-1+seg-2-retry"


def test_segments_of_another_prompt_are_made_again(changed_prompt_rig, tmp_path):
    first_task, second_task = changed_prompt_rig.adapter.submitted_tasks
    assert first_task.prompt == "Part 1 of 2. Show 0-8s of this shot.\nA pier at dusk"
    assert (tmp_path / "request-1" / "image.mp4").read_bytes() == b"seg-2-retry+seg-2-extra"


def test_a_failed_join_fails_at_once_and_keeps_the_segments(failed_join_rig, tmp_path):
    request = failed_join_rig.requests.find_by_id("request-1")
    assert request.status is GenerationStatus.FAILED
    assert request.error_message == "Joining the clip segments failed: ffmpeg exited 1: bad stream"
    assert (segment_dir(tmp_path) / "1.mp4").exists()
    assert (segment_dir(tmp_path) / "2.mp4").exists()
