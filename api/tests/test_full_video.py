import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from app.common.process import CommandError
from app.modules.ai_models.ai_caller import AiCaller
from app.modules.ai_models.ai_calls import (
    AiCallError,
    AiLimits,
    AiModelChoice,
    AiStepGroup,
    GoogleModelRequiredError,
)
from app.modules.ai_models.ai_images import AiImageEncoding
from app.modules.ai_models.gemini_client import GeminiClient
from app.modules.ai_models.step_models import AiStepModels
from app.modules.ai_models.streamed_answers import AiApiTools
from app.modules.jobs.film_analysis.full_video import (
    FullVideoPassTools,
    FullVideoPromptPasses,
    VideoCompressionError,
    VideoCompressor,
    VideoCompressorConfig,
    to_language_name,
)
from app.modules.jobs.film_analysis.media_parts import MediaPart
from app.modules.jobs.models import Job, JobOutputKind, JobStep, JobType
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.storage import JobStorage
from app.modules.jobs.video_to_markdown.ffmpeg_media import FfmpegMediaProcessor
from app.modules.providers.provider_catalog import ProviderId

JOB_ID = "job-1"
G4 = AiModelChoice(ProviderId.GOOGLE, "gemini-4-argon")
PASS_LIMITS = AiLimits(timeout_sec=900)
PART_DURATIONS_MS = {"part-01.mp4": 1_800_000, "part-02.mp4": 1_800_000, "part-03.mp4": 600_000}
PROMPTS = {"characterImage": "Image P", "characterVoice": "Voice P", "scene": "Scene P"}
PASS_STEPS = [
    JobStep.WRITING_CHARACTER_IMAGE_PROMPTS,
    JobStep.WRITING_CHARACTER_VOICE_PROMPTS,
    JobStep.WRITING_SCENE_PROMPTS,
]
PART_ANSWERS = ["## A", "## A\n## B", "## A\n## B\n## C", "V1", "V2", "V3", " S1 ", "S2", "S3"]
EARLIER_ANSWER_HEADING = "Your answer for the earlier parts:"
CHARACTERS_HEADING = "Characters:"


def build_job(language: str = "auto") -> Job:
    return Job(
        id=JOB_ID,
        type=JobType.FILM_ANALYSIS,
        options={"language": language, "prompts": PROMPTS, "inputMode": "full_video"},
    )


def write_parts(compression) -> None:
    for name in PART_DURATIONS_MS:
        (compression.output_dir / name).write_bytes(b"mp4")


def build_compressor(tmp_path):
    storage = JobStorage(tmp_path, max_upload_bytes=1024)
    media = MagicMock(spec=FfmpegMediaProcessor)
    media.compress_video.side_effect = write_parts
    media.probe_duration_ms.side_effect = lambda path: PART_DURATIONS_MS[path.name]
    compressor = VideoCompressor(
        storage, media, VideoCompressorConfig(part_sec=1800, max_side_px=480, max_fps=24)
    )
    return SimpleNamespace(compressor=compressor, storage=storage, media=media, steps=[])


def build_parts(tmp_path) -> list[MediaPart]:
    return [
        MediaPart(tmp_path / "part-01.mp4", 0, 1_800_000),
        MediaPart(tmp_path / "part-02.mp4", 1_800_000, 3_600_000),
        MediaPart(tmp_path / "part-03.mp4", 3_600_000, 4_200_000),
    ]


def build_mocked_passes(answers: list):
    repository = MagicMock(spec=JobRepository)
    ai_caller = MagicMock(spec=AiCaller)
    ai_caller.find_google_model.return_value = G4
    ai_caller.ask_for_text.side_effect = answers
    passes = FullVideoPromptPasses(FullVideoPassTools(repository, ai_caller, PASS_LIMITS))
    return SimpleNamespace(passes=passes, repository=repository, ai_caller=ai_caller, steps=[])


@pytest.fixture
def compressed(tmp_path):
    rig = build_compressor(tmp_path)
    stale_dir = rig.storage.compressed_dir(JOB_ID)
    stale_dir.mkdir(parents=True)
    (stale_dir / "part-09.mp4").write_bytes(b"old")
    parts = rig.compressor.compress(JOB_ID, tmp_path / "source.mp4", rig.steps.append)
    return SimpleNamespace(parts=parts, rig=rig)


@pytest.fixture
def compression_failure(tmp_path):
    rig = build_compressor(tmp_path)
    rig.media.compress_video.side_effect = CommandError(
        "ffmpeg exited with 1: Invalid data found when processing input"
    )
    with pytest.raises(VideoCompressionError) as caught:
        rig.compressor.compress(JOB_ID, tmp_path / "source.mp4", rig.steps.append)
    return SimpleNamespace(message=str(caught.value), rig=rig)


@pytest.fixture
def empty_compression(tmp_path):
    rig = build_compressor(tmp_path)
    rig.media.compress_video.side_effect = None
    with pytest.raises(VideoCompressionError) as caught:
        rig.compressor.compress(JOB_ID, tmp_path / "source.mp4", rig.steps.append)
    return str(caught.value)


@pytest.fixture
def three_part_passes(tmp_path):
    rig = build_mocked_passes(list(PART_ANSWERS))
    rig.passes.run(build_job(), build_parts(tmp_path), rig.steps.append)
    return SimpleNamespace(
        rig=rig,
        messages=[call.args[1].message for call in rig.ai_caller.ask_for_text.call_args_list],
        outputs={call.args[1]: call.args[2] for call in rig.repository.save_output.call_args_list},
    )


@pytest.fixture
def failing_image_pass(tmp_path):
    rig = build_mocked_passes(["## A", "## A\n## B", AiCallError("gemini failed: Internal error")])
    with pytest.raises(AiCallError) as caught:
        rig.passes.run(build_job(), build_parts(tmp_path), rig.steps.append)
    return SimpleNamespace(message=str(caught.value), rig=rig)


@pytest.fixture
def single_part_message(tmp_path):
    rig = build_mocked_passes(["## A", "V1", "S1"])
    rig.passes.run(build_job("vi"), build_parts(tmp_path)[:1], rig.steps.append)
    return rig.ai_caller.ask_for_text.call_args_list[0].args[1].message


@pytest.fixture
def claude_analysis_model(tmp_path):
    rig = build_mocked_passes([])
    rig.ai_caller.find_google_model.side_effect = GoogleModelRequiredError("Film analysis")
    with pytest.raises(GoogleModelRequiredError) as caught:
        rig.passes.run(build_job(), build_parts(tmp_path), rig.steps.append)
    return SimpleNamespace(message=str(caught.value), rig=rig)


def to_sse_answer(text: str) -> httpx.Response:
    chunk = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    return httpx.Response(200, text=f"data: {json.dumps(chunk)}\r\n\r\n")


@dataclass
class FakeGemini:
    answers: list[httpx.Response]
    requests: list[httpx.Request] = field(default_factory=list)

    def handle(self, request: httpx.Request) -> httpx.Response:
        request.read()
        self.requests.append(request)
        if request.method == "DELETE":
            return httpx.Response(200, json={})
        if request.url.params.get("upload_id"):
            number = request.url.params["upload_id"]
            stored_file = {
                "name": f"files/v{number}",
                "uri": f"https://files.test/v{number}",
                "state": "ACTIVE",
            }
            return httpx.Response(200, json={"file": stored_file})
        if request.url.path.endswith("/upload/v1beta/files"):
            number = sum(
                1
                for seen in self.requests
                if seen.url.path == request.url.path and not seen.url.params.get("upload_id")
            )
            upload_url = f"{request.url}?upload_id={number}"
            return httpx.Response(200, headers={"x-goog-upload-url": upload_url})
        return self.answers.pop(0)


@pytest.fixture
def gemini_passes(tmp_path):
    storage = JobStorage(tmp_path, max_upload_bytes=1024)
    compressed_dir = storage.compressed_dir(JOB_ID)
    compressed_dir.mkdir(parents=True)
    parts = [
        MediaPart(compressed_dir / "part-01.mp4", 0, 1_800_000),
        MediaPart(compressed_dir / "part-02.mp4", 1_800_000, 2_400_000),
    ]
    for part in parts:
        part.path.write_bytes(b"mp4")
    answers = ["## A", "## A\n## B", "V1", "V2", "S1", "S2"]
    fake = FakeGemini([to_sse_answer(answer) for answer in answers])
    step_models = MagicMock(spec=AiStepModels)
    step_models.find_google_model.return_value = G4
    gemini_client = GeminiClient(
        AiApiTools(
            httpx.Client(transport=httpx.MockTransport(fake.handle)),
            MagicMock(return_value="AIza-key"),
            AiImageEncoding(max_side_px=480, jpeg_quality=60),
        ),
        0,
    )
    FullVideoPromptPasses(
        FullVideoPassTools(
            MagicMock(spec=JobRepository),
            AiCaller({ProviderId.GOOGLE: gemini_client}, step_models),
            PASS_LIMITS,
        )
    ).run(build_job(), parts, lambda step: None)
    image_pass_requests = fake.requests[:8]
    return SimpleNamespace(
        calls=[(request.method, request.url.path) for request in image_pass_requests],
        streams=[
            json.loads(request.content)
            for request in image_pass_requests
            if "streamGenerateContent" in request.url.path
        ],
        compressed_names=sorted(path.name for path in compressed_dir.iterdir()),
    )


def test_compressing_reports_its_step_and_returns_timed_parts(compressed, tmp_path):
    directory = compressed.rig.storage.compressed_dir(JOB_ID)
    assert compressed.rig.steps == [JobStep.COMPRESSING_VIDEO]
    assert compressed.parts == [
        MediaPart(directory / "part-01.mp4", 0, 1_800_000),
        MediaPart(directory / "part-02.mp4", 1_800_000, 3_600_000),
        MediaPart(directory / "part-03.mp4", 3_600_000, 4_200_000),
    ]


def test_compressing_empties_the_folder_and_passes_the_limits(compressed, tmp_path):
    compression = compressed.rig.media.compress_video.call_args.args[0]
    assert not (compressed.rig.storage.compressed_dir(JOB_ID) / "part-09.mp4").exists()
    assert (
        compression.video_path,
        compression.part_sec,
        compression.max_side_px,
        compression.max_fps,
    ) == (tmp_path / "source.mp4", 1800, 480, 24)


def test_an_ffmpeg_error_fails_the_compression_and_removes_the_parts(compression_failure):
    assert compression_failure.message == (
        "Video compression failed: ffmpeg exited with 1: Invalid data found when processing input"
    )
    assert not compression_failure.rig.storage.compressed_dir(JOB_ID).exists()


def test_a_compression_without_parts_fails(empty_compression):
    assert empty_compression == "Video compression failed: ffmpeg wrote no video part"


def test_each_pass_sends_every_part_in_order(three_part_passes, tmp_path):
    calls = three_part_passes.rig.ai_caller.ask_for_text.call_args_list
    assert three_part_passes.rig.steps == PASS_STEPS
    assert [call.args[1].instructions for call in calls] == ["Image P"] * 3 + ["Voice P"] * 3 + [
        "Scene P"
    ] * 3
    assert [
        [(media.label, media.path.name, media.mime_type) for media in call.args[1].media]
        for call in calls[:3]
    ] == [
        [("[video 00:00–30:00]", "part-01.mp4", "video/mp4")],
        [("[video 30:00–1:00:00]", "part-02.mp4", "video/mp4")],
        [("[video 1:00:00–1:10:00]", "part-03.mp4", "video/mp4")],
    ]
    assert {(call.args[0], call.args[2]) for call in calls} == {(G4, PASS_LIMITS)}


def test_every_message_names_its_part_and_no_language_for_auto(three_part_passes):
    assert [message.split("\n\n")[:2] for message in three_part_passes.messages] == [
        [
            "The film is attached as video.",
            f"This part of the film runs from {start} to {end} (part {number} of 3).",
        ]
        for start, end, number in (
            ("00:00", "30:00", 1),
            ("30:00", "1:00:00", 2),
            ("1:00:00", "1:10:00", 3),
        )
    ] * 3


def test_image_and_voice_calls_carry_the_answer_of_the_previous_part(three_part_passes):
    messages = three_part_passes.messages
    assert EARLIER_ANSWER_HEADING not in messages[0]
    assert f"{EARLIER_ANSWER_HEADING}\n\n## A\n\n" in messages[1]
    assert f"{EARLIER_ANSWER_HEADING}\n\n## A\n## B\n\n" in messages[2]
    assert EARLIER_ANSWER_HEADING not in messages[3]
    assert f"{EARLIER_ANSWER_HEADING}\n\nV1\n\n" in messages[4]
    assert f"{EARLIER_ANSWER_HEADING}\n\nV2\n\n" in messages[5]
    assert all(EARLIER_ANSWER_HEADING not in message for message in messages[6:])


def test_voice_and_scene_calls_carry_the_stored_characters(three_part_passes):
    messages = three_part_passes.messages
    assert all(CHARACTERS_HEADING not in message for message in messages[:3])
    assert all(f"{CHARACTERS_HEADING}\n\n## A\n## B\n## C" in message for message in messages[3:])


def test_the_last_answer_is_stored_for_image_and_voice_and_every_scene_answer_joined(
    three_part_passes,
):
    assert three_part_passes.outputs == {
        JobOutputKind.CHARACTER_IMAGE_PROMPTS: "## A\n## B\n## C",
        JobOutputKind.CHARACTER_VOICE_PROMPTS: "V3",
        JobOutputKind.SCENE_PROMPTS: "S1\n\nS2\n\nS3",
    }


def test_each_pass_records_the_google_model(three_part_passes):
    assert [call.args for call in three_part_passes.rig.repository.save_ai_used.call_args_list] == [
        (JOB_ID, step, G4) for step in PASS_STEPS
    ]
    three_part_passes.rig.ai_caller.find_google_model.assert_called_with(AiStepGroup.FILM_ANALYSIS)


def test_a_failing_part_stores_nothing_and_stops_the_passes(failing_image_pass):
    assert failing_image_pass.message == "gemini failed: Internal error"
    assert failing_image_pass.rig.steps == [JobStep.WRITING_CHARACTER_IMAGE_PROMPTS]
    failing_image_pass.rig.repository.save_output.assert_not_called()


def test_a_single_part_film_names_no_part_but_the_spoken_language(single_part_message):
    assert single_part_message == "The film is attached as video.\nSpoken language: Vietnamese"


def test_a_pass_on_another_provider_fails_before_any_call(claude_analysis_model):
    assert claude_analysis_model.message == "Film analysis needs a Google AI model — open Settings"
    claude_analysis_model.rig.ai_caller.ask_for_text.assert_not_called()


@pytest.mark.parametrize(
    ("language", "expected"),
    [("auto", None), ("vi", "Vietnamese"), ("ja", "Japanese"), ("de", "de")],
)
def test_the_language_name_comes_from_the_job_language(language, expected):
    assert to_language_name({"language": language}) == expected


def test_a_job_without_a_language_names_none():
    assert to_language_name({}) is None


def test_a_full_video_pass_uploads_each_part_for_its_call_and_deletes_it(gemini_passes):
    stream_path = "/v1beta/models/gemini-4-argon:streamGenerateContent"
    assert gemini_passes.calls == [
        ("POST", "/upload/v1beta/files"),
        ("POST", "/upload/v1beta/files"),
        ("POST", stream_path),
        ("DELETE", "/v1beta/files/v1"),
        ("POST", "/upload/v1beta/files"),
        ("POST", "/upload/v1beta/files"),
        ("POST", stream_path),
        ("DELETE", "/v1beta/files/v2"),
    ]


def test_a_full_video_call_ends_with_the_part_as_video(gemini_passes):
    assert [stream["contents"][0]["parts"][-2:] for stream in gemini_passes.streams] == [
        [
            {"text": "[video 00:00–30:00]"},
            {"fileData": {"mimeType": "video/mp4", "fileUri": "https://files.test/v1"}},
        ],
        [
            {"text": "[video 30:00–40:00]"},
            {"fileData": {"mimeType": "video/mp4", "fileUri": "https://files.test/v2"}},
        ],
    ]
    assert all("inlineData" not in json.dumps(stream) for stream in gemini_passes.streams)


def test_a_full_video_call_asks_for_low_resolution_and_free_text(gemini_passes):
    assert [stream["generationConfig"] for stream in gemini_passes.streams] == [
        {"mediaResolution": "MEDIA_RESOLUTION_LOW"}
    ] * 2
    assert all("videoMetadata" not in json.dumps(stream) for stream in gemini_passes.streams)


def test_the_compressed_parts_stay_after_the_passes(gemini_passes):
    assert gemini_passes.compressed_names == ["part-01.mp4", "part-02.mp4"]
