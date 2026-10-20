import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest

from app.common.process import CommandError
from app.modules.ai_models.ai_caller import AiCaller, AiClient
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
from app.modules.app_settings.service import AppSettingService
from app.modules.jobs.film_analysis.audio_listener import (
    AudioListener,
    AudioListenerConfig,
    AudioListenerTools,
    AudioPreparationError,
    AudioSource,
)
from app.modules.jobs.film_analysis.audio_notes import SPEAKERS_AND_SOUNDS_SCHEMA
from app.modules.jobs.models import Job, JobStep, JobType
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.storage import JobStorage
from app.modules.jobs.video_to_markdown.ffmpeg_media import FfmpegMediaProcessor
from app.modules.jobs.video_to_markdown.transcript import TranscriptSegment
from app.modules.providers.provider_catalog import ProviderId

JOB_ID = "job-1"
G38 = AiModelChoice(ProviderId.GOOGLE, "gemini-3.8-flash")
CLI = AiModelChoice(ProviderId.CLAUDE_CLI, "default")
AUDIO_LIMITS = AiLimits(timeout_sec=900)
PART_DURATIONS_MS = {"part-01.m4a": 1_800_000, "part-02.m4a": 1_800_000, "part-03.m4a": 600_000}
SEGMENTS = [
    TranscriptSegment(start_ms=10_000, end_ms=12_000, text=" Chào anh."),
    TranscriptSegment(start_ms=1_810_000, end_ms=1_812_000, text=" Chào em."),
    TranscriptSegment(start_ms=3_700_000, end_ms=3_702_000, text=" Đi thôi."),
]
PART_REPLIES = [
    {
        "speakers": [{"name": "Mai", "voice": "young woman, soft voice"}, {"name": "Long"}],
        "lines": [{"atMs": 10_000, "speaker": "Mai"}],
        "sounds": [],
    },
    {
        "speakers": [{"name": "Mai", "voice": "young woman"}, {"name": "Ba", "voice": "old man"}],
        "lines": [{"atMs": 1_810_000, "speaker": "Long"}],
        "sounds": [{"atMs": 2_000_000, "kind": "music", "description": "drums start"}],
    },
    {"speakers": [], "lines": [], "sounds": []},
]
INTERNAL_ERROR = httpx.Response(500, json={"error": {"message": "Internal error"}})
STREAM_PATH_PART = ":streamGenerateContent"


def to_sse_answer(reply: dict) -> httpx.Response:
    chunk = {"candidates": [{"content": {"parts": [{"text": json.dumps(reply)}]}}]}
    return httpx.Response(200, text=f"data: {json.dumps(chunk)}\r\n\r\n")


@dataclass
class FakeGemini:
    answers: list[httpx.Response]
    upload_state: str = "ACTIVE"
    requests: list[httpx.Request] = field(default_factory=list)

    def handle(self, request: httpx.Request) -> httpx.Response:
        request.read()
        self.requests.append(request)
        upload_count = len(self.uploads())
        if request.method == "DELETE":
            return httpx.Response(200, json={})
        if request.url.params.get("upload_id"):
            number = request.url.params["upload_id"]
            return httpx.Response(200, json={"file": self.to_file(number, "PROCESSING")})
        if request.url.path.endswith("/upload/v1beta/files"):
            upload_url = f"{request.url}?upload_id={upload_count}"
            return httpx.Response(200, headers={"x-goog-upload-url": upload_url})
        if request.method == "GET":
            return httpx.Response(200, json=self.to_file(request.url.path[-1], self.upload_state))
        return self.answers.pop(0)

    def to_file(self, number: str, state: str) -> dict:
        return {"name": f"files/f{number}", "uri": f"https://files.test/f{number}", "state": state}

    def uploads(self) -> list[httpx.Request]:
        return [
            request
            for request in self.requests
            if request.url.path.endswith("/upload/v1beta/files")
            and not request.url.params.get("upload_id")
        ]

    def streams(self) -> list[dict]:
        return [
            json.loads(request.content)
            for request in self.requests
            if STREAM_PATH_PART in request.url.path
        ]

    def deleted_paths(self) -> list[str]:
        return [request.url.path for request in self.requests if request.method == "DELETE"]


def write_parts(split) -> None:
    for name in PART_DURATIONS_MS:
        (split.output_dir / name).write_bytes(b"aac")


def build_job() -> Job:
    return Job(
        id=JOB_ID,
        type=JobType.FILM_ANALYSIS,
        options={"prompts": {"speakersAndSounds": "Hear P"}, "inputMode": "whole_video"},
    )


def build_rig(tmp_path, fake: FakeGemini, audio_choice: AiModelChoice = G38):
    storage = JobStorage(tmp_path, max_upload_bytes=1024)
    repository = MagicMock(spec=JobRepository)
    media = MagicMock(spec=FfmpegMediaProcessor)
    media.split_audio.side_effect = write_parts
    media.probe_duration_ms.side_effect = lambda path: PART_DURATIONS_MS[path.name]
    settings_service = MagicMock(spec=AppSettingService)
    settings_service.get_ai_model.return_value = CLI
    settings_service.get_ai_step_models.return_value = {AiStepGroup.AUDIO: audio_choice}
    http_client = httpx.Client(transport=httpx.MockTransport(fake.handle))
    claude_client = MagicMock(spec=AiClient)
    gemini_client = GeminiClient(
        AiApiTools(
            http_client,
            MagicMock(return_value="AIza-key"),
            AiImageEncoding(max_side_px=480, jpeg_quality=60),
        ),
        0,
    )
    ai_caller = AiCaller(
        {ProviderId.GOOGLE: gemini_client, ProviderId.CLAUDE_CLI: claude_client},
        AiStepModels(settings_service, lambda provider: True),
    )
    listener = AudioListener(
        AudioListenerTools(storage, repository, media, ai_caller),
        AudioListenerConfig(part_sec=1800, limits=AUDIO_LIMITS),
    )
    return SimpleNamespace(
        listener=listener,
        storage=storage,
        repository=repository,
        media=media,
        fake=fake,
        claude_client=claude_client,
        steps=[],
    )


def listen(rig) -> object:
    return rig.listener.listen(
        AudioSource(build_job(), rig.storage.source_path(JOB_ID, "a.mp4"), SEGMENTS, 4_200_000),
        rig.steps.append,
    )


def capture_listen_error(rig, error_class: type[Exception]):
    with pytest.raises(error_class) as caught:
        listen(rig)
    return SimpleNamespace(message=str(caught.value), rig=rig)


@pytest.fixture
def heard(tmp_path):
    rig = build_rig(tmp_path, FakeGemini([to_sse_answer(reply) for reply in PART_REPLIES]))
    notes = listen(rig)
    return SimpleNamespace(
        rig=rig,
        notes=notes,
        streams=rig.fake.streams(),
        notes_file=json.loads(rig.storage.audio_notes_path(JOB_ID).read_text(encoding="utf-8")),
    )


@pytest.fixture
def messages(heard):
    return [stream["contents"][0]["parts"][0]["text"] for stream in heard.streams]


@pytest.fixture
def unreadable_audio(tmp_path):
    rig = build_rig(tmp_path, FakeGemini([]))
    rig.media.split_audio.side_effect = CommandError(
        "ffmpeg exited with 1: Invalid data found when processing input"
    )
    return capture_listen_error(rig, AudioPreparationError)


@pytest.fixture
def silent_audio(tmp_path):
    rig = build_rig(tmp_path, FakeGemini([]))
    rig.media.split_audio.side_effect = None
    return capture_listen_error(rig, AudioPreparationError)


@pytest.fixture
def failed_upload(tmp_path):
    return capture_listen_error(build_rig(tmp_path, FakeGemini([], "FAILED")), AiCallError)


@pytest.fixture
def second_part_failure(tmp_path):
    rig = build_rig(tmp_path, FakeGemini([to_sse_answer(PART_REPLIES[0]), INTERNAL_ERROR]))
    rig.storage.audio_notes_path(JOB_ID).parent.mkdir(parents=True)
    rig.storage.audio_notes_path(JOB_ID).write_text("{}", encoding="utf-8")
    return capture_listen_error(rig, AiCallError)


@pytest.fixture
def claude_audio_model(tmp_path):
    return capture_listen_error(build_rig(tmp_path, FakeGemini([]), CLI), GoogleModelRequiredError)


def test_listening_reports_its_step_and_records_the_audio_model(heard):
    assert heard.rig.steps == [JobStep.LISTENING_TO_AUDIO]
    heard.rig.repository.save_ai_used.assert_called_once_with(
        JOB_ID, JobStep.LISTENING_TO_AUDIO, G38
    )


def test_each_part_is_uploaded_and_asked_in_time_order(heard):
    assert [
        request.headers["x-goog-upload-header-content-type"] for request in heard.rig.fake.uploads()
    ] == ["audio/mp4"] * 3
    assert [stream["contents"][0]["parts"][1:] for stream in heard.streams] == [
        [
            {"text": "[audio 00:00–30:00]"},
            {"fileData": {"mimeType": "audio/mp4", "fileUri": "https://files.test/f1"}},
        ],
        [
            {"text": "[audio 30:00–1:00:00]"},
            {"fileData": {"mimeType": "audio/mp4", "fileUri": "https://files.test/f2"}},
        ],
        [
            {"text": "[audio 1:00:00–1:10:00]"},
            {"fileData": {"mimeType": "audio/mp4", "fileUri": "https://files.test/f3"}},
        ],
    ]


def test_each_call_carries_the_prompt_and_the_reply_schema(heard):
    assert {
        (
            stream["systemInstruction"]["parts"][0]["text"],
            json.dumps(stream["generationConfig"]["responseJsonSchema"]),
        )
        for stream in heard.streams
    } == {("Hear P", json.dumps(SPEAKERS_AND_SOUNDS_SCHEMA))}


def test_the_first_part_message_has_no_speakers(messages):
    assert messages[0] == (
        "This part of the film runs from 00:00 to 30:00.\n\nTranscript:\n[10000ms] Chào anh."
    )


def test_later_part_messages_list_the_speakers_so_far(messages):
    assert messages[1] == (
        "This part of the film runs from 30:00 to 1:00:00.\n\n"
        "Speakers so far:\n- Mai — young woman, soft voice\n- Long\n"
        "Use the same name for the same voice.\n\n"
        "Transcript:\n[1810000ms] Chào em."
    )
    assert messages[2].startswith(
        "This part of the film runs from 1:00:00 to 1:10:00.\n\n"
        "Speakers so far:\n- Mai — young woman, soft voice\n- Long\n- Ba — old man\n"
    )
    assert messages[2].endswith("Transcript:\n[3700000ms] Đi thôi.")


def test_every_uploaded_file_is_deleted_and_the_parts_are_removed(heard):
    assert heard.rig.fake.deleted_paths() == [
        "/v1beta/files/f1",
        "/v1beta/files/f2",
        "/v1beta/files/f3",
    ]
    assert not heard.rig.storage.audio_dir(JOB_ID).exists()


def test_the_audio_notes_are_saved_for_the_later_steps(heard):
    assert heard.notes_file == {
        "speakers": [
            {"name": "Mai", "voice": "young woman, soft voice"},
            {"name": "Long", "voice": ""},
            {"name": "Ba", "voice": "old man"},
        ],
        "lines": [
            {"atMs": 10_000, "speaker": "Mai"},
            {"atMs": 1_810_000, "speaker": "Long"},
        ],
        "sounds": [{"atMs": 2_000_000, "kind": "music", "description": "drums start"}],
    }


def test_the_audio_is_cut_into_parts_of_the_set_length(heard):
    split = heard.rig.media.split_audio.call_args.args[0]
    assert (split.part_sec, split.output_dir) == (1800, heard.rig.storage.audio_dir(JOB_ID))


def test_an_ffmpeg_error_fails_the_preparation_before_any_call(unreadable_audio):
    assert unreadable_audio.message == (
        "Audio preparation failed: ffmpeg exited with 1: Invalid data found when processing input"
    )
    assert unreadable_audio.rig.fake.requests == []
    assert not unreadable_audio.rig.storage.audio_dir(JOB_ID).exists()


def test_a_video_without_audio_parts_fails_the_preparation(silent_audio):
    assert silent_audio.message == "Audio preparation failed: ffmpeg wrote no audio part"


def test_an_upload_that_ends_failed_fails_the_step(failed_upload):
    assert failed_upload.message == "gemini could not take the audio: FAILED"
    assert failed_upload.rig.fake.deleted_paths() == ["/v1beta/files/f1"]
    assert not failed_upload.rig.storage.audio_dir(JOB_ID).exists()


def test_a_failing_part_stops_the_step_and_keeps_nothing(second_part_failure):
    rig = second_part_failure.rig
    assert second_part_failure.message == "gemini failed: Internal error"
    assert len(rig.fake.uploads()) == 2
    assert rig.fake.deleted_paths() == ["/v1beta/files/f1", "/v1beta/files/f2"]
    assert not rig.storage.audio_notes_path(JOB_ID).exists()
    assert not rig.storage.audio_dir(JOB_ID).exists()


def test_an_audio_model_of_another_provider_fails_before_any_work(claude_audio_model):
    rig = claude_audio_model.rig
    assert claude_audio_model.message == "Audio needs a Google AI model — open Settings"
    rig.media.split_audio.assert_not_called()
    rig.claude_client.ask_for_json.assert_not_called()
    assert rig.fake.requests == []
