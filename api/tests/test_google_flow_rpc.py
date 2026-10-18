import json
from collections.abc import Callable
from types import SimpleNamespace

import pytest

from app.modules.media_generation.adapters.google_flow_rpc import (
    CAPTCHA_IMAGE,
    CAPTCHA_SLOT,
    FlowAnswerError,
    FlowOperation,
    FlowRpc,
    FlowRpcError,
    ImageGeneration,
    build_create_project_rpc,
    build_image_rpc,
    build_media_rpc,
    find_media_id_in_listing,
    read_created_project_id,
    read_operation,
    read_payload,
    read_uploaded_media_id,
    read_video_url,
)

MEDIA_ID = "11111111-2222-3333-4444-555555555555"


def to_envelope_line(*entries: list) -> str:
    return json.dumps(list(entries))


def to_inner(rpc: FlowRpc) -> list:
    return json.loads(json.loads(rpc.freq)[0][0][1])


def capture(error_type: type[Exception], call: Callable[[], object]) -> Exception:
    with pytest.raises(error_type) as caught:
        call()
    return caught.value


@pytest.fixture
def chunked_payload():
    answer_text = "\n".join(
        [
            ")]}'",
            "",
            "57",
            to_envelope_line(["wrb.fr", "other", "[1]"], ["di", 12], "not a list"),
            "[[broken",
            to_envelope_line(["wrb.fr", "as29s", json.dumps(["media"]), None, None, None]),
            "42",
            "[1, 2]",
        ]
    )
    return read_payload(answer_text, "as29s")


@pytest.fixture
def unwrapped_payload():
    return read_payload(to_envelope_line(["wrb.fr", "as29s", ["already", "decoded"]]), "as29s")


@pytest.fixture
def rpc_error_details():
    with_code = capture(
        FlowRpcError,
        lambda: read_payload(
            to_envelope_line(["wrb.fr", "ogiZ0b", None, None, None, [8]]), "ogiZ0b"
        ),
    )
    without_code = capture(
        FlowRpcError, lambda: read_payload(to_envelope_line(["wrb.fr", "ogiZ0b"]), "ogiZ0b")
    )
    return SimpleNamespace(with_code=with_code, without_code=without_code)


@pytest.fixture
def missing_envelope_error():
    return capture(
        FlowAnswerError,
        lambda: read_payload(to_envelope_line(["wrb.fr", "other", "[]"]), "as29s"),
    )


@pytest.fixture
def plain_rpc_params():
    return build_media_rpc(MEDIA_ID).to_params()


@pytest.fixture(params=[("   ", "video-tool project"), ("A" * 200, "A" * 160)])
def project_title(request):
    raw_title, expected_title = request.param
    inner = to_inner(build_create_project_rpc(raw_title))
    return SimpleNamespace(actual=inner[1][1][0], expected=expected_title)


@pytest.fixture
def edit_image_inner():
    rpc = build_image_rpc(
        ImageGeneration(
            prompt="Make the boat blue",
            project_id="fp-1",
            model_id="NARWHAL",
            aspect=2,
            reference_media_ids=("source-1", "ref-1"),
            base_media_id="source-1",
        )
    )
    return SimpleNamespace(rpc=rpc, inner=to_inner(rpc))


@pytest.fixture(params=[(["fp-1", ["Title"]], "fp-1"), (["x" * 36], "x" * 36)])
def created_project_id(request):
    payload, expected = request.param
    return SimpleNamespace(actual=read_created_project_id(payload), expected=expected)


@pytest.fixture(params=[[], [None], [""], ["x" * 37]])
def bad_created_project_error(request):
    return capture(FlowAnswerError, lambda: read_created_project_id(request.param))


@pytest.fixture(params=[[], [[]], [[""]], "text"])
def bad_upload_error(request):
    return capture(FlowAnswerError, lambda: read_uploaded_media_id(request.param))


@pytest.fixture(
    params=[
        (["op-1", "fp-1", "scene", "CAE"], FlowOperation("op-1", "CAE", None)),
        (["op-1", "fp-1", "scene"], FlowOperation("op-1", None, None)),
        (
            ["op-1", "fp-1", "scene", "RUN", None, [0] * 8 + [[4, [None, "Media not found."]]]],
            FlowOperation("op-1", "RUN", "Media not found."),
        ),
        (
            ["op-1", "fp-1", "scene", "RUN", None, [0] * 8 + [[4]]],
            FlowOperation("op-1", "RUN", "operation failed without a message"),
        ),
        (
            ["op-1", "fp-1", "scene", "RUN", None, [0] * 8 + [[3]]],
            FlowOperation("op-1", "RUN", None),
        ),
        (
            ["op-1", "fp-1", "scene", "RUN", None, [0] * 8 + [[]]],
            FlowOperation("op-1", "RUN", None),
        ),
    ]
)
def operation_outcome(request):
    record, expected = request.param
    return SimpleNamespace(actual=read_operation([None, 50, [record]]), expected=expected)


@pytest.fixture(params=[[], [None, 50, []], [None, 50, [[None]]], [None, 50, ["op"]]])
def bad_operation_error(request):
    return capture(FlowAnswerError, lambda: read_operation(request.param))


@pytest.fixture(
    params=[
        (f'["op-1",null,["t",[1,2],true,null,null,"{MEDIA_ID}"]]', MEDIA_ID),
        (f'[\\"OP-1\\",null,null,\\"{MEDIA_ID}\\"]', MEDIA_ID),
        ('["op-1",null,["t"]]', None),
        (f'["op-2",null,null,"{MEDIA_ID}"]', None),
    ]
)
def listing_media_id(request):
    listing_text, expected = request.param
    return SimpleNamespace(actual=find_media_id_in_listing(listing_text, "op-1"), expected=expected)


@pytest.fixture(
    params=[
        (
            [
                "http://flow-content.google/video/a",
                ["https://flow-content.google/image/b", "https://flow-content.google/video/c"],
            ],
            "https://flow-content.google/video/c",
        ),
        (["https://flow-content.google/image/b"], None),
    ]
)
def video_url(request):
    payload, expected = request.param
    return SimpleNamespace(actual=read_video_url(payload), expected=expected)


def test_payload_is_found_among_chunks_and_noise(chunked_payload):
    assert chunked_payload == ["media"]


def test_payload_already_decoded_is_returned_as_is(unwrapped_payload):
    assert unwrapped_payload == ["already", "decoded"]


def test_error_slot_becomes_an_rpc_error(rpc_error_details):
    assert rpc_error_details.with_code.code == 8
    assert str(rpc_error_details.with_code) == "ogiZ0b failed: [8]"
    assert rpc_error_details.without_code.code is True


def test_missing_envelope_is_an_answer_error(missing_envelope_error):
    assert str(missing_envelope_error) == "no as29s answer in the response (1 others)"


def test_rpc_without_captcha_or_match_sends_only_the_envelope(plain_rpc_params):
    assert sorted(plain_rpc_params) == ["freq", "rpcid"]


def test_project_title_is_cleaned(project_title):
    assert project_title.actual == project_title.expected


def test_edit_sends_the_source_as_base_image_once(edit_image_inner):
    assert edit_image_inner.rpc.captcha_action == CAPTCHA_IMAGE
    assert edit_image_inner.inner[1][0][2] == [
        ["source-1", None, None, None, 2],
        ["ref-1", None, None, None, 1],
    ]
    assert edit_image_inner.inner[3][4] == "source-1"
    assert edit_image_inner.inner[3][10] == [CAPTCHA_SLOT, 1]


def test_created_project_id_is_read(created_project_id):
    assert created_project_id.actual == created_project_id.expected


def test_created_project_without_a_usable_id_fails(bad_created_project_error):
    assert str(bad_created_project_error) == "the new Flow project carried no id"


def test_upload_without_a_media_id_fails(bad_upload_error):
    assert str(bad_upload_error) == "the upload carried no media id"


def test_operation_record_is_read(operation_outcome):
    assert operation_outcome.actual == operation_outcome.expected


def test_operation_without_a_record_fails(bad_operation_error):
    assert str(bad_operation_error) == "the operation carried no record"


def test_listing_media_id_is_found_next_to_the_operation(listing_media_id):
    assert listing_media_id.actual == listing_media_id.expected


def test_video_url_is_the_first_https_video(video_url):
    assert video_url.actual == video_url.expected
