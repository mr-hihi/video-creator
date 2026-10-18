import base64
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from app.modules.media_generation.adapters.flow_project_owners import (
    FlowProjectOwner,
    FlowProjectOwnerKind,
    FlowProjectOwners,
)
from app.modules.media_generation.adapters.google_flow import (
    INPUT_EXPIRED_MESSAGE,
    MISSING_INPUT_MESSAGE,
    NO_FLOW_PROJECT_MESSAGE,
    CaptchaRpcPacer,
    GoogleFlowAdapter,
    GoogleFlowTools,
    PacerClock,
)
from app.modules.media_generation.media_task import (
    MediaInputs,
    MediaResult,
    MediaTask,
    PollOutcome,
    ProviderError,
    ProviderErrorKind,
    SubmitOutcome,
)
from app.modules.providers.errors import ExtensionNotConnectedError
from app.modules.providers.model_catalog import CatalogModel
from app.modules.providers.provider_catalog import MediaKind

FLOW_PROJECT_ID = "fp-1"
CREATED_PROJECT_ID = "fp-new"
FALLBACK_PROJECT_ID = "594758cc-0000-4000-8000-000000000000"
NANO_PRO = CatalogModel("GEM_PIX_2", "Nano Banana Pro")
VEO_LITE = CatalogModel("veo_3_1_i2v_lite", "Veo 3.1 Lite", clip_lengths_s=(8,))
OMNI = CatalogModel("abra_i2v_{n}s", "Omni Flash", clip_lengths_s=(4, 6, 8, 10))
IMAGE_URL = "https://flow-content.google/image/img-1?sig=abc"
VIDEO_URL = "https://flow-content.google/video/vid-1?sig=abc"
POSTER_URL = "https://flow-content.google/image/poster-1?sig=abc"
JPEG_BYTES = b"jpeg-bytes"
MP4_BYTES = b"mp4-bytes"
MEDIA_ID = "11111111-2222-3333-4444-555555555555"
EXTERNAL_ID = f"{FLOW_PROJECT_ID}|op-1"
ANSWER_PREFIX = ")]}'\n\n"
PROJECT_OWNER = FlowProjectOwner(
    FlowProjectOwnerKind.FILM_PROJECT, "project-1", "Harbor", FLOW_PROJECT_ID
)
NEW_OWNER = FlowProjectOwner(FlowProjectOwnerKind.FILM_PROJECT, "project-2", "Pier", None)


def batch_answer(rpc_id: str, payload: Any) -> dict[str, Any]:
    envelope = json.dumps([["wrb.fr", rpc_id, json.dumps(payload), None, None, None, "generic"]])
    return {"status": 200, "data": f"{ANSWER_PREFIX}{len(envelope)}\n{envelope}"}


def rpc_error_answer(rpc_id: str, code: int, extra_text: str = "") -> dict[str, Any]:
    envelope = json.dumps([["wrb.fr", rpc_id, None, None, None, [code], "generic"]])
    return {"status": 400, "data": f"{ANSWER_PREFIX}{envelope}{extra_text}"}


def extension_error(text: str) -> dict[str, Any]:
    return {"status": 502, "error": text}


def upload_answer(media_id: str) -> dict[str, Any]:
    return batch_answer("maseQ", [[media_id, FLOW_PROJECT_ID, "upload-op", "CAE"]])


def operation_answer(status: str, outcome: list[Any] | None = None) -> dict[str, Any]:
    record = ["op-1", FLOW_PROJECT_ID, "scene-1", status, None, [None] * 8 + [outcome]]
    return batch_answer("jwpduf", [None, 50, [record]])


IMAGE_ANSWER = batch_answer("ogiZ0b", [None, [[None, [IMAGE_URL]]]])
VIDEO_ANSWER = batch_answer("eb1hJf", [None, 50, [["op-1", FLOW_PROJECT_ID, "scene-1", "RUN"]]])
CREATED_ANSWER = batch_answer("jHPbke", [CREATED_PROJECT_ID, ["Pier"]])
LISTING_ANSWER = {"status": 200, "data": f'["op-1",null,["t",[1,2],true,null,null,"{MEDIA_ID}"]]'}
EMPTY_LISTING_ANSWER = {"status": 200, "data": ""}
MEDIA_ANSWER = batch_answer("as29s", [MEDIA_ID, [POSTER_URL, VIDEO_URL]])
POSTER_ONLY_ANSWER = batch_answer("as29s", [MEDIA_ID, [POSTER_URL]])


@dataclass
class FakeBridge:
    answers: list[dict[str, Any] | Exception]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def call(self, method: str, params: dict[str, Any], timeout_sec: float) -> dict[str, Any]:
        self.calls.append({"method": method, **params, "timeout_sec": timeout_sec})
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def rpc_ids(self) -> list[str]:
        return [call["rpcid"] for call in self.calls]

    def inner_of(self, index: int) -> Any:
        return json.loads(json.loads(self.calls[index]["freq"])[0][0][1])


@dataclass
class FakeClock:
    now_sec: float = 100.0
    sleeps_sec: list[float] = field(default_factory=list)

    def read(self) -> float:
        return self.now_sec

    def sleep(self, seconds: float) -> None:
        self.sleeps_sec.append(seconds)
        self.now_sec += seconds


@dataclass
class FlowRig:
    adapter: GoogleFlowAdapter
    bridge: FakeBridge
    owners: MagicMock
    clock: FakeClock
    downloads: list[httpx.Request]


def build_rig(
    answers: list[dict[str, Any] | Exception],
    owner: FlowProjectOwner | None = PROJECT_OWNER,
    download_status: int = 200,
) -> FlowRig:
    bridge = FakeBridge(list(answers))
    owners = MagicMock(spec=FlowProjectOwners)
    owners.find_owner.return_value = owner
    clock = FakeClock()
    downloads: list[httpx.Request] = []

    def answer_download(request: httpx.Request) -> httpx.Response:
        downloads.append(request)
        if download_status != 200:
            return httpx.Response(download_status)
        if "/video/" in request.url.path:
            return httpx.Response(200, content=MP4_BYTES, headers={"content-type": "video/mp4"})
        return httpx.Response(200, content=JPEG_BYTES, headers={"content-type": "image/jpeg"})

    adapter = GoogleFlowAdapter(
        GoogleFlowTools(
            bridge, httpx.Client(transport=httpx.MockTransport(answer_download)), owners
        ),
        CaptchaRpcPacer(PacerClock(clock.read, clock.sleep)),
    )
    return FlowRig(adapter, bridge, owners, clock, downloads)


def build_task(media_kind: MediaKind, **overrides: Any) -> MediaTask:
    fields = {
        "request_id": "request-1",
        "media_kind": media_kind,
        "model": NANO_PRO,
        "api_key": None,
        "base_url": None,
        "prompt": "A pier at dawn",
        "inputs": MediaInputs(),
        "aspect": "16:9",
    }
    return MediaTask(**{**fields, **overrides})


def capture_error(call: Callable[[], object]) -> ProviderError:
    with pytest.raises(ProviderError) as caught:
        call()
    return caught.value


@pytest.fixture
def red_png(tmp_path):
    path = tmp_path / "red.png"
    path.write_bytes(b"red")
    return path


@pytest.fixture
def blue_png(tmp_path):
    path = tmp_path / "blue.png"
    path.write_bytes(b"blue")
    return path


@pytest.fixture
def image_with_references(red_png, blue_png):
    rig = build_rig([upload_answer("media-red"), upload_answer("media-blue"), IMAGE_ANSWER])
    task = build_task(MediaKind.IMAGE, inputs=MediaInputs(references=(red_png, blue_png)))
    outcome = rig.adapter.submit(task)
    return SimpleNamespace(
        outcome=outcome,
        rig=rig,
        captcha_actions=[call["captchaAction"] for call in rig.bridge.calls],
        upload_inner=rig.bridge.inner_of(0),
        image_item=rig.bridge.inner_of(2)[1][0],
    )


@pytest.fixture
def reused_reference_rpc_ids(red_png):
    rig = build_rig([upload_answer("media-red"), IMAGE_ANSWER, IMAGE_ANSWER])
    task = build_task(MediaKind.IMAGE, inputs=MediaInputs(references=(red_png,)))
    rig.adapter.submit(task)
    rig.adapter.submit(task)
    return rig.bridge.rpc_ids()


@pytest.fixture
def edit_inner(red_png, blue_png):
    rig = build_rig([upload_answer("media-src"), upload_answer("media-ref"), IMAGE_ANSWER])
    task = build_task(
        MediaKind.EDIT_IMAGE,
        inputs=MediaInputs(source_image=red_png, references=(blue_png,)),
        aspect="9:16",
    )
    rig.adapter.submit(task)
    return rig.bridge.inner_of(2)


@pytest.fixture(
    params=[
        (OMNI, 8, "9:16", "abra_i2v_8s", 1),
        (VEO_LITE, None, "16:9", "veo_3_1_i2v_lite", 2),
    ],
    ids=["omni portrait", "veo landscape"],
)
def clip_submit(request, red_png):
    model, clip_length_s, aspect, expected_model_id, expected_aspect = request.param
    rig = build_rig([upload_answer("media-start"), VIDEO_ANSWER])
    task = build_task(
        MediaKind.VIDEO,
        model=model,
        inputs=MediaInputs(start_frame=red_png),
        aspect=aspect,
        clip_length_s=clip_length_s,
    )
    outcome = rig.adapter.submit(task)
    return SimpleNamespace(
        outcome=outcome,
        call=rig.bridge.calls[1],
        request=rig.bridge.inner_of(1)[0][0],
        expected_model_id=expected_model_id,
        expected_aspect=expected_aspect,
    )


@pytest.fixture(
    params=[
        (MediaKind.EDIT_IMAGE, NANO_PRO, False, "An edit needs the image to edit"),
        (MediaKind.VIDEO, VEO_LITE, False, "A clip needs a start image"),
        (MediaKind.SPEECH, NANO_PRO, False, "Google Flow does not make speech"),
        (MediaKind.VIDEO, OMNI, True, "Omni Flash needs a clip length"),
    ],
    ids=["edit without source", "clip without start", "speech", "omni without length"],
)
def unusable_task_error(request, red_png):
    media_kind, model, has_start_frame, expected_message = request.param
    rig = build_rig([upload_answer("media-start")])
    inputs = MediaInputs(start_frame=red_png if has_start_frame else None)
    task = build_task(media_kind, model=model, inputs=inputs)
    error = capture_error(lambda: rig.adapter.submit(task))
    return SimpleNamespace(error=error, expected_message=expected_message)


@pytest.fixture(
    params=[
        (NEW_OWNER, [CREATED_ANSWER], CREATED_PROJECT_ID, 1),
        (NEW_OWNER, [extension_error("NO_AT_TOKEN")], FALLBACK_PROJECT_ID, 0),
        (NEW_OWNER, [batch_answer("jHPbke", [])], FALLBACK_PROJECT_ID, 0),
        (None, [], FALLBACK_PROJECT_ID, 0),
    ],
    ids=["created", "creation fails", "creation answer unreadable", "no owner"],
)
def flow_project_choice(request):
    owner, project_answers, expected_project_id, expected_save_count = request.param
    rig = build_rig([*project_answers, IMAGE_ANSWER], owner=owner)
    rig.adapter.submit(build_task(MediaKind.IMAGE, flow_project_id=FALLBACK_PROJECT_ID))
    return SimpleNamespace(
        actual=(
            rig.bridge.inner_of(len(project_answers))[3][5],
            rig.owners.save_flow_project_id.call_count,
        ),
        expected=(expected_project_id, expected_save_count),
    )


@pytest.fixture
def created_project_save_args():
    rig = build_rig([CREATED_ANSWER, IMAGE_ANSWER], owner=NEW_OWNER)
    rig.adapter.submit(build_task(MediaKind.IMAGE))
    return rig.owners.save_flow_project_id.call_args.args


@pytest.fixture(
    params=[(NEW_OWNER, [extension_error("NO_AT_TOKEN")]), (None, [])],
    ids=["creation fails", "no owner"],
)
def no_flow_project_error(request):
    owner, answers = request.param
    rig = build_rig(answers, owner=owner)
    return capture_error(lambda: rig.adapter.submit(build_task(MediaKind.IMAGE)))


@pytest.fixture
def creation_not_connected_error():
    rig = build_rig([ExtensionNotConnectedError()], owner=NEW_OWNER)
    return capture_error(
        lambda: rig.adapter.submit(build_task(MediaKind.IMAGE, flow_project_id=FALLBACK_PROJECT_ID))
    )


@pytest.fixture(
    params=[
        (
            extension_error("[HIJACK] extension_hijack_detected"),
            ProviderErrorKind.NOT_CONNECTED,
            "Google Flow flagged the captcha (extension_hijack_detected)",
        ),
        (
            rpc_error_answer("ogiZ0b", 7, ' "PUBLIC_ERROR_UNUSUAL_ACTIVITY"'),
            ProviderErrorKind.UNUSUAL_ACTIVITY,
            "Google Flow reported unusual activity",
        ),
        (
            extension_error("UNSUPPORTED_ON_BATCH_API: video upscale"),
            ProviderErrorKind.FATAL,
            "Google Flow cannot do this: UNSUPPORTED_ON_BATCH_API: video upscale",
        ),
        (
            rpc_error_answer("ogiZ0b", 3, ' "PUBLIC_ERROR_UNSAFE_GENERATION"'),
            ProviderErrorKind.FATAL,
            "Blocked by the content filter: PUBLIC_ERROR_UNSAFE_GENERATION",
        ),
        (
            extension_error("CAPTCHA_FAILED: execute_hang\n    at mint (injected.js:1)"),
            ProviderErrorKind.CAPTCHA,
            "Google Flow captcha failed: CAPTCHA_FAILED: execute_hang",
        ),
        (
            extension_error(f"NO_AT_TOKEN   {'A' * 60}"),
            ProviderErrorKind.RETRYABLE,
            "Google Flow failed: NO_AT_TOKEN …",
        ),
        (
            rpc_error_answer("ogiZ0b", 8),
            ProviderErrorKind.RETRYABLE,
            "Google Flow failed: ogiZ0b answered error code [8]",
        ),
        (
            batch_answer("ogiZ0b", [None, []]),
            ProviderErrorKind.RETRYABLE,
            "Google Flow failed: no image in the answer",
        ),
        (
            {"status": 200},
            ProviderErrorKind.RETRYABLE,
            "Google Flow failed: no ogiZ0b answer in the response (0 others)",
        ),
        (
            ExtensionNotConnectedError(),
            ProviderErrorKind.NOT_CONNECTED,
            "The Google Flow extension is not connected",
        ),
        (
            TimeoutError("late"),
            ProviderErrorKind.NO_ANSWER,
            "Google Flow did not answer within 300 s",
        ),
    ],
    ids=[
        "hijack",
        "unusual activity",
        "unsupported",
        "content filter",
        "captcha",
        "other extension error",
        "rpc error",
        "no image",
        "empty answer",
        "not connected",
        "timeout",
    ],
)
def classified_failure(request):
    answer, expected_kind, expected_message = request.param
    rig = build_rig([answer])
    error = capture_error(lambda: rig.adapter.submit(build_task(MediaKind.IMAGE)))
    return SimpleNamespace(
        actual=(error.kind, str(error)), expected=(expected_kind, expected_message)
    )


@pytest.fixture
def image_download_error():
    rig = build_rig([IMAGE_ANSWER], download_status=500)
    return capture_error(lambda: rig.adapter.submit(build_task(MediaKind.IMAGE)))


@pytest.fixture
def expired_reference(red_png):
    rig = build_rig(
        [
            upload_answer("media-red"),
            IMAGE_ANSWER,
            rpc_error_answer("ogiZ0b", 5),
            upload_answer("media-red-2"),
            IMAGE_ANSWER,
        ]
    )
    task = build_task(MediaKind.IMAGE, inputs=MediaInputs(references=(red_png,)))
    rig.adapter.submit(task)
    error = capture_error(lambda: rig.adapter.submit(task))
    rig.adapter.submit(task)
    return SimpleNamespace(
        error=error,
        rpc_ids=rig.bridge.rpc_ids(),
        last_inputs=rig.bridge.inner_of(4)[1][0][2],
    )


@pytest.fixture
def not_found_without_reuse_error(red_png):
    rig = build_rig([upload_answer("media-red"), extension_error("Requested entity was not found")])
    task = build_task(MediaKind.IMAGE, inputs=MediaInputs(references=(red_png,)))
    return capture_error(lambda: rig.adapter.submit(task))


@pytest.fixture
def pacer_sleeps():
    clock = FakeClock(now_sec=0.0)
    pacer = CaptchaRpcPacer(PacerClock(clock.read, clock.sleep))
    pacer.wait_turn()
    clock.now_sec += 1.0
    pacer.wait_turn()
    clock.now_sec += 10.0
    pacer.wait_turn()
    return clock.sleeps_sec


@pytest.fixture
def first_round_poll():
    rig = build_rig([operation_answer("RUN")])
    outcome = rig.adapter.poll(build_task(MediaKind.VIDEO), EXTERNAL_ID)
    return SimpleNamespace(outcome=outcome, rpc_ids=rig.bridge.rpc_ids())


@pytest.fixture
def finished_poll():
    rig = build_rig(
        [operation_answer("CAE"), LISTING_ANSWER, MEDIA_ANSWER, operation_answer("RUN")]
    )
    task = build_task(MediaKind.VIDEO)
    outcome = rig.adapter.poll(task, EXTERNAL_ID)
    rig.adapter.poll(task, EXTERNAL_ID)
    return SimpleNamespace(
        outcome=outcome,
        rig=rig,
        listing_call=rig.bridge.calls[1],
        listing_inner=rig.bridge.inner_of(1),
    )


@pytest.fixture(
    params=[
        ([operation_answer("RUN")] * 3, 3),
        ([operation_answer("RUN", [4, [None, "Media not found."]])], 1),
        ([extension_error("NO_AT_TOKEN")], 1),
    ],
    ids=["every third round", "complaint", "unreadable operation"],
)
def listing_lookup(request):
    operation_answers, poll_count = request.param
    rig = build_rig([*operation_answers, EMPTY_LISTING_ANSWER])
    task = build_task(MediaKind.VIDEO)
    outcomes = [rig.adapter.poll(task, EXTERNAL_ID) for _ in range(poll_count)]
    return SimpleNamespace(
        outcomes=outcomes,
        last_rpc_id=rig.bridge.rpc_ids()[-1],
        expected_outcomes=[PollOutcome(is_done=False)] * poll_count,
    )


@pytest.fixture
def poster_then_video_polls():
    rig = build_rig([operation_answer("CAE"), LISTING_ANSWER, POSTER_ONLY_ANSWER, MEDIA_ANSWER])
    task = build_task(MediaKind.VIDEO)
    outcomes = [rig.adapter.poll(task, EXTERNAL_ID) for _ in range(2)]
    return SimpleNamespace(
        is_done_by_round=[outcome.is_done for outcome in outcomes], rpc_ids=rig.bridge.rpc_ids()
    )


@pytest.fixture
def failed_media_lookup_polls():
    rig = build_rig(
        [
            operation_answer("CAE"),
            LISTING_ANSWER,
            extension_error("NO_AT_TOKEN"),
            operation_answer("RUN"),
        ]
    )
    task = build_task(MediaKind.VIDEO)
    outcomes = [rig.adapter.poll(task, EXTERNAL_ID) for _ in range(2)]
    return SimpleNamespace(outcomes=outcomes, rpc_ids=rig.bridge.rpc_ids())


@pytest.fixture
def disconnected_poll():
    rig = build_rig([ExtensionNotConnectedError(), ExtensionNotConnectedError()])
    outcome = rig.adapter.poll(build_task(MediaKind.VIDEO), EXTERNAL_ID)
    return SimpleNamespace(outcome=outcome, rpc_ids=rig.bridge.rpc_ids())


@pytest.fixture
def failed_download_poll():
    rig = build_rig([operation_answer("CAE"), LISTING_ANSWER, MEDIA_ANSWER], download_status=500)
    return rig.adapter.poll(build_task(MediaKind.VIDEO), EXTERNAL_ID)


@pytest.fixture(params=["op-1", "|op-1", "fp-1|"])
def unknown_operation_error(request):
    rig = build_rig([])
    return capture_error(lambda: rig.adapter.poll(build_task(MediaKind.VIDEO), request.param))


def test_image_uploads_each_reference_then_generates(image_with_references):
    assert image_with_references.rig.bridge.rpc_ids() == ["maseQ", "maseQ", "ogiZ0b"]
    assert image_with_references.captcha_actions == [
        "IMAGE_GENERATION",
        "IMAGE_GENERATION",
        "IMAGE_GENERATION",
    ]
    assert image_with_references.rig.bridge.calls[2]["timeout_sec"] == 300.0


def test_upload_sends_the_file_into_the_flow_project(image_with_references):
    assert image_with_references.upload_inner[0][5] == FLOW_PROJECT_ID
    assert image_with_references.upload_inner[1] == base64.b64encode(b"red").decode()
    assert image_with_references.upload_inner[2] == "image/png"
    assert image_with_references.upload_inner[8] == "red.png"


def test_image_request_carries_references_model_aspect_and_prompt(image_with_references):
    assert image_with_references.image_item[2] == [
        ["media-red", None, None, None, 1],
        ["media-blue", None, None, None, 1],
    ]
    assert image_with_references.image_item[4] == 3
    assert image_with_references.image_item[5] == "GEM_PIX_2"
    assert image_with_references.image_item[7][5] == FLOW_PROJECT_ID
    assert image_with_references.image_item[8] == [[["A pier at dawn"]]]


def test_image_result_is_downloaded_at_once(image_with_references):
    assert image_with_references.outcome == SubmitOutcome(
        result=MediaResult(content=JPEG_BYTES, file_extension="jpg")
    )
    assert str(image_with_references.rig.downloads[0].url) == IMAGE_URL


def test_captcha_calls_are_spaced_three_seconds_apart(image_with_references):
    assert image_with_references.rig.clock.sleeps_sec == [3.0, 3.0]


def test_a_reference_is_uploaded_once(reused_reference_rpc_ids):
    assert reused_reference_rpc_ids == ["maseQ", "ogiZ0b", "ogiZ0b"]


def test_edit_sends_the_source_as_base_image(edit_inner):
    assert edit_inner[1][0][2] == [
        ["media-src", None, None, None, 2],
        ["media-ref", None, None, None, 1],
    ]
    assert edit_inner[1][0][4] == 2
    assert edit_inner[3][4] == "media-src"


def test_clip_is_started_from_the_uploaded_frame(clip_submit):
    assert clip_submit.outcome == SubmitOutcome(external_id=EXTERNAL_ID)
    assert clip_submit.call["rpcid"] == "eb1hJf"
    assert clip_submit.call["captchaAction"] == "VIDEO_GENERATION"
    assert clip_submit.request[1] == clip_submit.expected_model_id
    assert clip_submit.request[2] == clip_submit.expected_aspect
    assert clip_submit.request[4][1] == "media-start"


def test_unusable_task_fails_at_once(unusable_task_error):
    assert unusable_task_error.error.kind is ProviderErrorKind.FATAL
    assert str(unusable_task_error.error) == unusable_task_error.expected_message


def test_flow_project_is_created_or_falls_back(flow_project_choice):
    assert flow_project_choice.actual == flow_project_choice.expected


def test_created_flow_project_is_saved_on_its_owner(created_project_save_args):
    assert created_project_save_args == (NEW_OWNER, CREATED_PROJECT_ID)


def test_no_flow_project_fails_the_request(no_flow_project_error):
    assert no_flow_project_error.kind is ProviderErrorKind.FATAL
    assert str(no_flow_project_error) == NO_FLOW_PROJECT_MESSAGE


def test_project_creation_without_the_extension_requeues(creation_not_connected_error):
    assert creation_not_connected_error.kind is ProviderErrorKind.NOT_CONNECTED


def test_flow_answers_map_to_retry_kinds(classified_failure):
    assert classified_failure.actual == classified_failure.expected


def test_image_download_failure_is_retried(image_download_error):
    assert image_download_error.kind is ProviderErrorKind.RETRYABLE
    assert str(image_download_error) == "Could not download the result: HTTP 500"


def test_expired_reference_is_uploaded_again(expired_reference):
    assert expired_reference.error.kind is ProviderErrorKind.INPUT_EXPIRED
    assert str(expired_reference.error) == INPUT_EXPIRED_MESSAGE
    assert expired_reference.rpc_ids == ["maseQ", "ogiZ0b", "ogiZ0b", "maseQ", "ogiZ0b"]
    assert expired_reference.last_inputs == [["media-red-2", None, None, None, 1]]


def test_not_found_on_fresh_uploads_is_counted(not_found_without_reuse_error):
    assert not_found_without_reuse_error.kind is ProviderErrorKind.RETRYABLE
    assert str(not_found_without_reuse_error) == MISSING_INPUT_MESSAGE


def test_pacer_waits_only_for_the_rest_of_the_gap(pacer_sleeps):
    assert pacer_sleeps == [2.0]


def test_first_poll_round_skips_the_listing(first_round_poll):
    assert first_round_poll.outcome == PollOutcome(is_done=False)
    assert first_round_poll.rpc_ids == ["jwpduf"]


def test_finished_clip_is_found_and_downloaded(finished_poll):
    assert finished_poll.outcome == PollOutcome(
        is_done=True, result=MediaResult(content=MP4_BYTES, file_extension="mp4")
    )
    assert str(finished_poll.rig.downloads[0].url) == VIDEO_URL
    assert finished_poll.rig.clock.sleeps_sec == []


def test_listing_is_searched_for_the_operation(finished_poll):
    assert finished_poll.listing_call["match"] == "op-1"
    assert finished_poll.listing_inner[0] == f"projects/{FLOW_PROJECT_ID}"


def test_finished_operation_is_forgotten(finished_poll):
    assert finished_poll.rig.bridge.rpc_ids() == ["jwpduf", "Zzl0ze", "as29s", "jwpduf"]


def test_listing_is_read_when_worth_it(listing_lookup):
    assert listing_lookup.outcomes == listing_lookup.expected_outcomes
    assert listing_lookup.last_rpc_id == "Zzl0ze"


def test_poster_without_video_keeps_polling_from_the_known_media(poster_then_video_polls):
    assert poster_then_video_polls.is_done_by_round == [False, True]
    assert poster_then_video_polls.rpc_ids == ["jwpduf", "Zzl0ze", "as29s", "as29s"]


def test_failed_media_lookup_starts_over(failed_media_lookup_polls):
    assert failed_media_lookup_polls.outcomes == [
        PollOutcome(is_done=False),
        PollOutcome(is_done=False),
    ]
    assert failed_media_lookup_polls.rpc_ids == ["jwpduf", "Zzl0ze", "as29s", "jwpduf"]


def test_poll_without_the_extension_keeps_waiting(disconnected_poll):
    assert disconnected_poll.outcome == PollOutcome(is_done=False)
    assert disconnected_poll.rpc_ids == ["jwpduf", "Zzl0ze"]


def test_failed_clip_download_keeps_waiting(failed_download_poll):
    assert failed_download_poll == PollOutcome(is_done=False)


def test_unknown_operation_id_fails(unknown_operation_error):
    assert unknown_operation_error.kind is ProviderErrorKind.FATAL
    assert str(unknown_operation_error) == "Unknown Google Flow operation id"
