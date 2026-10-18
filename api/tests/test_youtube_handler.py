from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.common.process import CommandError
from app.modules.ai_models.ai_caller import AiCaller
from app.modules.ai_models.ai_calls import AiLimits, AiModelChoice
from app.modules.jobs.models import Job, JobStatus, JobStep, JobType
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.storage import JobStorage
from app.modules.jobs.video_to_markdown.ffmpeg_media import FfmpegMediaProcessor
from app.modules.jobs.video_to_markdown.frame_sampler import FrameSampler
from app.modules.jobs.video_to_markdown.handler import NoSpeechError
from app.modules.jobs.video_to_markdown.moment_steps import (
    KeyMomentPicker,
    MomentFrameCapturer,
    MomentPickerConfig,
    MomentPickingSteps,
)
from app.modules.jobs.youtube_to_markdown.captions import (
    CaptionKind,
    CaptionTrack,
    MissingCaptionLanguageError,
    NoCaptionsError,
)
from app.modules.jobs.youtube_to_markdown.handler import (
    YoutubeToMarkdownHandler,
    YoutubeToMarkdownTools,
)
from app.modules.jobs.youtube_to_markdown.transcript_fetcher import YoutubeTranscriptFetcher
from app.modules.jobs.youtube_to_markdown.ytdlp_downloader import YtDlpDownloader
from app.modules.prompt_presets.prompt_texts import DEFAULT_PRESET_PROMPTS
from app.modules.providers.provider_catalog import ProviderId

JOB_ID = "job-1"
VIDEO_ID = "vfjegxHDOwI"
VIDEO_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
SOURCE_FILENAME = f"Đầu tư [{VIDEO_ID}].mp4"
JOB_OPTIONS = {
    "url": VIDEO_URL,
    "videoId": VIDEO_ID,
    "language": "auto",
    "prompts": {"videoToMarkdown": "Pick the investing lessons."},
}
VIDEO_INFO = {
    "id": VIDEO_ID,
    "title": "Đầu tư",
    "duration": 670,
    "live_status": "not_live",
    "language": "vi",
    "subtitles": {},
    "automatic_captions": {"en": [], "vi-orig": []},
}
CAPTIONS_JSON = {
    "events": [
        {"tStartMs": 0, "dDurationMs": 4000, "segs": [{"utf8": "Xin chào"}]},
        {"tStartMs": 83_000, "dDurationMs": 2000, "segs": [{"utf8": "Bài học đầu tiên"}]},
    ]
}
OUTLINE_REPLY = {
    "title": "Kinh nghiệm đầu tư",
    "summary": "Tóm tắt.",
    "moments": [{"atMs": 83_000, "title": "Bài học"}, {"atMs": 0, "title": "Mở đầu"}],
}
PICKER_CONFIG = MomentPickerConfig(AiLimits(timeout_sec=600), {ProviderId.CLAUDE_CLI: 300})


def build_job() -> Job:
    return Job(
        id=JOB_ID,
        type=JobType.YOUTUBE_TO_MARKDOWN,
        status=JobStatus.PROCESSING,
        source_filename=SOURCE_FILENAME,
        options=dict(JOB_OPTIONS),
    )


def build_downloader(video_info: dict, captions_json: dict) -> YtDlpDownloader:
    downloader = MagicMock(spec=YtDlpDownloader)
    downloader.read_video_info.return_value = video_info
    downloader.download_captions.return_value = captions_json
    downloader.download_video.side_effect = lambda video_url, output_path: output_path
    return downloader


def capture_handle_error(handler: YoutubeToMarkdownHandler, error_class: type[Exception]):
    with pytest.raises(error_class) as caught:
        handler.handle(build_job(), lambda step: None)
    return caught.value


@pytest.fixture
def storage(tmp_path):
    return JobStorage(tmp_path, max_upload_bytes=1024)


@pytest.fixture
def repository():
    return MagicMock(spec=JobRepository)


def write_samples(sampling) -> None:
    for second in range(sampling.frame_count):
        (sampling.output_pattern.parent / f"sample-{second:05d}.jpg").write_bytes(b"jpeg")


@pytest.fixture
def media():
    processor = MagicMock(spec=FfmpegMediaProcessor)
    processor.sample_frames.side_effect = write_samples
    return processor


@pytest.fixture
def ai_caller():
    caller = MagicMock(spec=AiCaller)
    caller.find_model.return_value = AiModelChoice(ProviderId.CLAUDE_CLI, "default")
    caller.ask_for_json.return_value = OUTLINE_REPLY
    return caller


@pytest.fixture
def downloader():
    return build_downloader(VIDEO_INFO, CAPTIONS_JSON)


@pytest.fixture
def handler(storage, repository, media, ai_caller, downloader):
    tools = YoutubeToMarkdownTools(
        transcript_fetcher=YoutubeTranscriptFetcher(downloader, repository, storage),
        downloader=downloader,
        moment_steps=MomentPickingSteps(
            KeyMomentPicker(ai_caller, repository, PICKER_CONFIG),
            FrameSampler(storage, media, 512),
        ),
        frame_capturer=MomentFrameCapturer(storage, media),
    )
    return YoutubeToMarkdownHandler(storage, tools, max_moments=5)


@pytest.fixture
def reported_steps(handler):
    steps: list[JobStep] = []
    handler.handle(build_job(), steps.append)
    return steps


@pytest.fixture
def written_markdown(storage, reported_steps):
    return storage.markdown_path(JOB_ID, SOURCE_FILENAME).read_text(encoding="utf-8")


@pytest.fixture
def captured_frames(media, reported_steps):
    return [(call.args[0].name, call.args[1]) for call in media.capture_frame.call_args_list]


@pytest.fixture
def picked_ask(ai_caller, reported_steps):
    return ai_caller.ask_for_json.call_args.args[1]


@pytest.fixture
def whole_video_run(handler, ai_caller, downloader, media):
    job = build_job()
    job.options["inputMode"] = "whole_video"
    steps: list[JobStep] = []
    handler.handle(job, steps.append)
    return SimpleNamespace(
        steps=steps,
        ask=ai_caller.ask_for_json.call_args.args[1],
        download_count=downloader.download_video.call_count,
        sampled_video=media.sample_frames.call_args.args[0].video_path.name,
    )


@pytest.fixture
def unprompted_job_instructions(handler, ai_caller):
    job = build_job()
    job.options = {"url": VIDEO_URL, "videoId": VIDEO_ID, "language": "auto"}
    handler.handle(job, lambda step: None)
    return ai_caller.ask_for_json.call_args.args[1].instructions


@pytest.fixture
def no_captions_error(handler, downloader):
    downloader.read_video_info.return_value = {**VIDEO_INFO, "automatic_captions": {}}
    return capture_handle_error(handler, NoCaptionsError)


@pytest.fixture
def missing_language_error(handler):
    job = build_job()
    job.options["language"] = "en"
    with pytest.raises(MissingCaptionLanguageError) as caught:
        handler.handle(job, lambda step: None)
    return caught.value


@pytest.fixture
def no_speech_error(handler, downloader):
    downloader.download_captions.return_value = {"events": [{"segs": [{"utf8": "[Âm nhạc]"}]}]}
    return capture_handle_error(handler, NoSpeechError)


@pytest.fixture
def download_error(handler, downloader):
    downloader.download_video.side_effect = CommandError(
        f"yt-dlp exited with 1: ERROR: [youtube] {VIDEO_ID}: Sign in to confirm you're not a bot"
    )
    return capture_handle_error(handler, CommandError)


def test_handle_reports_the_youtube_steps_in_order(reported_steps):
    assert reported_steps == [
        JobStep.FETCHING_TRANSCRIPT,
        JobStep.PICKING_MOMENTS,
        JobStep.DOWNLOADING_VIDEO,
        JobStep.CAPTURING_FRAMES,
        JobStep.WRITING_MARKDOWN,
    ]


def test_handle_saves_the_caption_kind_of_the_chosen_track(repository, reported_steps):
    repository.merge_options.assert_called_once_with(JOB_ID, {"captionKind": "auto"})


def test_handle_picks_moments_with_the_job_prompt(picked_ask):
    assert (picked_ask.instructions, "at most 5 key moments" in picked_ask.message) == (
        "Pick the investing lessons.",
        True,
    )


def test_handle_in_whole_video_mode_downloads_before_picking(whole_video_run):
    assert whole_video_run.steps == [
        JobStep.FETCHING_TRANSCRIPT,
        JobStep.DOWNLOADING_VIDEO,
        JobStep.SAMPLING_FRAMES,
        JobStep.PICKING_MOMENTS,
        JobStep.CAPTURING_FRAMES,
        JobStep.WRITING_MARKDOWN,
    ]


def test_handle_in_whole_video_mode_downloads_once_and_samples_it(whole_video_run):
    assert (whole_video_run.download_count, whole_video_run.sampled_video) == (1, "source.mp4")


def test_handle_in_whole_video_mode_splits_670_samples_into_windows(whole_video_run):
    assert len(whole_video_run.ask.images) == 70


def test_handle_falls_back_to_the_default_prompt(unprompted_job_instructions):
    assert unprompted_job_instructions == DEFAULT_PRESET_PROMPTS.video_to_markdown


def test_handle_downloads_the_chosen_caption_track(downloader, storage, reported_steps):
    downloader.download_captions.assert_called_once_with(
        VIDEO_URL, CaptionTrack("vi-orig", CaptionKind.AUTO), storage.work_dir(JOB_ID)
    )


def test_handle_downloads_the_video_as_the_job_source(downloader, storage, reported_steps):
    downloader.download_video.assert_called_once_with(
        VIDEO_URL, storage.source_path(JOB_ID, SOURCE_FILENAME)
    )


def test_handle_captures_frames_from_the_downloaded_video(captured_frames):
    assert captured_frames == [("source.mp4", 0), ("source.mp4", 83_000)]


def test_handle_writes_the_youtube_link_as_the_source(written_markdown):
    assert f"> Source: {VIDEO_URL} · Duration: 11:10 · Language: vi" in written_markdown


def test_handle_links_each_heading_to_its_second(written_markdown):
    assert f"## [01:23]({VIDEO_URL}&t=83s) — Bài học" in written_markdown
    assert "![01:23 — Bài học](images/moment-02-01m23s.jpg)" in written_markdown


def test_handle_writes_the_result_archive(storage, reported_steps):
    assert storage.archive_path(JOB_ID).is_file()


def test_handle_stops_before_any_download_without_captions(no_captions_error, downloader):
    assert str(no_captions_error) == "This video has no transcript on YouTube"
    downloader.download_captions.assert_not_called()
    downloader.download_video.assert_not_called()


def test_handle_refuses_a_machine_translated_language(missing_language_error, repository):
    assert str(missing_language_error) == (
        "No 'en' captions on YouTube for this video. Available: vi (auto)"
    )
    repository.merge_options.assert_not_called()


def test_handle_raises_when_the_captions_hold_no_speech(no_speech_error, downloader):
    assert str(no_speech_error) == "No speech was detected in the video"
    downloader.download_video.assert_not_called()


def test_handle_lets_a_download_failure_fail_the_job(download_error, media):
    assert "not a bot" in str(download_error)
    media.capture_frame.assert_not_called()
