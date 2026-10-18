from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.ai_models.ai_caller import AiCaller
from app.modules.ai_models.ai_calls import AiLimits, AiModelChoice
from app.modules.jobs.models import Job, JobStatus, JobStep, JobType
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.storage import JobStorage
from app.modules.jobs.video_to_markdown.ffmpeg_media import FfmpegMediaProcessor
from app.modules.jobs.video_to_markdown.frame_sampler import FrameSampler
from app.modules.jobs.video_to_markdown.handler import (
    NoSpeechError,
    VideoToMarkdownHandler,
    VideoToMarkdownTools,
)
from app.modules.jobs.video_to_markdown.moment_steps import (
    KeyMomentPicker,
    MomentPickerConfig,
    MomentPickingSteps,
    to_frame_filename,
)
from app.modules.jobs.video_to_markdown.transcript import Transcript, TranscriptSegment
from app.modules.jobs.video_to_markdown.whisper_transcriber import WhisperCppTranscriber
from app.modules.prompt_presets.prompt_texts import DEFAULT_PRESET_PROMPTS
from app.modules.providers.provider_catalog import ProviderId

JOB_ID = "job-1"
SOURCE_FILENAME = "My demo.mp4"
JOB_PROMPT = "Prompt one"
TRANSCRIPT = Transcript(
    language="vi",
    segments=[
        TranscriptSegment(start_ms=0, end_ms=4000, text=" Xin chào."),
        TranscriptSegment(start_ms=10_000, end_ms=12_000, text=" Mở trang cài đặt."),
    ],
)
OUTLINE_REPLY = {
    "title": "Hướng dẫn",
    "summary": "Tóm tắt.",
    "moments": [{"atMs": 10_000, "title": "Cài đặt"}, {"atMs": 0, "title": "Mở đầu"}],
}
PICKER_CONFIG = MomentPickerConfig(AiLimits(timeout_sec=600), {ProviderId.CLAUDE_CLI: 100})


@dataclass(frozen=True)
class Outcome:
    actual: str
    expected: str


def build_job(**options) -> Job:
    return Job(
        id=JOB_ID,
        type=JobType.VIDEO_TO_MARKDOWN,
        status=JobStatus.PROCESSING,
        source_filename=SOURCE_FILENAME,
        options={"language": "vi", "prompts": {"videoToMarkdown": JOB_PROMPT}, **options},
    )


def write_samples(sampling) -> None:
    for second in range(sampling.frame_count):
        (sampling.output_pattern.parent / f"sample-{second:05d}.jpg").write_bytes(b"jpeg")


def build_tools(storage: JobStorage, transcript: Transcript, outline_reply: dict):
    media = MagicMock(spec=FfmpegMediaProcessor)
    media.probe_duration_ms.return_value = 60_000
    media.extract_audio.side_effect = lambda video_path, audio_path: audio_path
    media.sample_frames.side_effect = write_samples
    transcriber = MagicMock(spec=WhisperCppTranscriber)
    transcriber.transcribe.return_value = transcript
    ai_caller = MagicMock(spec=AiCaller)
    ai_caller.find_model.return_value = AiModelChoice(ProviderId.CLAUDE_CLI, "default")
    ai_caller.ask_for_json.return_value = outline_reply
    moment_steps = MomentPickingSteps(
        KeyMomentPicker(ai_caller, MagicMock(spec=JobRepository), PICKER_CONFIG),
        FrameSampler(storage, media, 512),
    )
    return SimpleNamespace(
        handler_tools=VideoToMarkdownTools(
            media=media, transcriber=transcriber, moment_steps=moment_steps
        ),
        media=media,
        transcriber=transcriber,
        ai_caller=ai_caller,
    )


@pytest.fixture
def storage(tmp_path):
    return JobStorage(tmp_path, max_upload_bytes=1024)


@pytest.fixture
def tools(storage):
    return build_tools(storage, TRANSCRIPT, OUTLINE_REPLY)


@pytest.fixture
def reported_steps(storage, tools):
    steps: list[JobStep] = []
    VideoToMarkdownHandler(storage, tools.handler_tools, max_moments=5).handle(
        build_job(), steps.append
    )
    return steps


@pytest.fixture
def whole_video_run(storage, tools):
    steps: list[JobStep] = []
    VideoToMarkdownHandler(storage, tools.handler_tools, max_moments=5).handle(
        build_job(inputMode="whole_video"), steps.append
    )
    return SimpleNamespace(steps=steps, ask=tools.ai_caller.ask_for_json.call_args.args[1])


@pytest.fixture
def written_markdown(storage, reported_steps):
    return storage.markdown_path(JOB_ID, SOURCE_FILENAME).read_text(encoding="utf-8")


@pytest.fixture
def untitled_markdown(storage):
    tools = build_tools(storage, TRANSCRIPT, {"title": "", "summary": "", "moments": []})
    VideoToMarkdownHandler(storage, tools.handler_tools, max_moments=5).handle(
        build_job(), lambda step: None
    )
    return storage.markdown_path(JOB_ID, SOURCE_FILENAME).read_text(encoding="utf-8")


@pytest.fixture
def captured_positions_ms(tools, reported_steps):
    return [call.args[1] for call in tools.media.capture_frame.call_args_list]


@pytest.fixture
def picked_ask(tools, reported_steps):
    return tools.ai_caller.ask_for_json.call_args.args[1]


@pytest.fixture
def unprompted_job_instructions(storage, tools):
    job = build_job()
    job.options = {"language": "auto"}
    VideoToMarkdownHandler(storage, tools.handler_tools, max_moments=5).handle(
        job, lambda step: None
    )
    return tools.ai_caller.ask_for_json.call_args.args[1].instructions


@pytest.fixture
def no_speech_tools(storage):
    return build_tools(storage, Transcript(language="vi", segments=[]), OUTLINE_REPLY)


@pytest.fixture
def no_speech_error(storage, no_speech_tools):
    handler = VideoToMarkdownHandler(storage, no_speech_tools.handler_tools, max_moments=5)
    with pytest.raises(NoSpeechError) as caught:
        handler.handle(build_job(), lambda step: None)
    return caught.value


@pytest.fixture(
    params=[(1, 83_000, "moment-01-01m23s.jpg"), (12, 3_723_000, "moment-12-1h02m03s.jpg")]
)
def frame_filename(request):
    index, at_ms, expected = request.param
    return Outcome(actual=to_frame_filename(index, at_ms), expected=expected)


def test_handle_reports_every_step_in_order(reported_steps):
    assert reported_steps == [
        JobStep.EXTRACTING_AUDIO,
        JobStep.TRANSCRIBING,
        JobStep.PICKING_MOMENTS,
        JobStep.CAPTURING_FRAMES,
        JobStep.WRITING_MARKDOWN,
    ]


def test_handle_transcribes_with_the_job_language(tools, reported_steps, storage):
    tools.transcriber.transcribe.assert_called_once_with(
        storage.work_dir(JOB_ID) / "audio.wav", "vi"
    )


def test_handle_captures_one_frame_per_moment_in_time_order(captured_positions_ms):
    assert captured_positions_ms == [0, 10_000]


def test_handle_picks_moments_with_the_job_prompt(picked_ask):
    assert (picked_ask.instructions, "at most 5 key moments" in picked_ask.message) == (
        JOB_PROMPT,
        True,
    )


def test_handle_sends_no_frame_in_subtitles_mode(picked_ask):
    assert list(picked_ask.images) == []


def test_handle_in_whole_video_mode_samples_frames_before_picking(whole_video_run):
    assert whole_video_run.steps == [
        JobStep.EXTRACTING_AUDIO,
        JobStep.TRANSCRIBING,
        JobStep.SAMPLING_FRAMES,
        JobStep.PICKING_MOMENTS,
        JobStep.CAPTURING_FRAMES,
        JobStep.WRITING_MARKDOWN,
    ]


def test_handle_in_whole_video_mode_sends_one_frame_per_second(whole_video_run):
    assert [image.label for image in whole_video_run.ask.images][:3] == [
        "[0ms]",
        "[1000ms]",
        "[2000ms]",
    ]
    assert len(whole_video_run.ask.images) == 60


def test_handle_in_whole_video_mode_deletes_the_samples(storage, whole_video_run):
    assert not storage.samples_dir(JOB_ID).exists()


def test_handle_falls_back_to_the_default_prompt(unprompted_job_instructions):
    assert unprompted_job_instructions == DEFAULT_PRESET_PROMPTS.video_to_markdown


def test_handle_writes_markdown_with_moment_images(written_markdown):
    assert (
        "## 00:10 — Cài đặt\n\n![00:10 — Cài đặt](images/moment-02-00m10s.jpg)" in written_markdown
    )


def test_handle_writes_the_result_archive(storage, reported_steps):
    assert storage.archive_path(JOB_ID).is_file()


def test_handle_titles_the_document_after_the_file_when_claude_gives_none(untitled_markdown):
    assert untitled_markdown.startswith("# My demo\n")


def test_handle_raises_when_no_speech_is_detected(no_speech_error):
    assert str(no_speech_error) == "No speech was detected in the video"


def test_handle_skips_moment_picking_without_speech(no_speech_tools, no_speech_error):
    no_speech_tools.ai_caller.ask_for_json.assert_not_called()


def test_to_frame_filename_encodes_index_and_position(frame_filename):
    assert frame_filename.actual == frame_filename.expected
