from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.ai_models.ai_caller import AiCaller
from app.modules.ai_models.ai_calls import AiCallError, AiLimits, AiModelChoice, AiStepGroup
from app.modules.jobs.errors import NoVideoNotesError
from app.modules.jobs.film_analysis.frame_steps import FilmFrameSteps, FilmFrameTools
from app.modules.jobs.film_analysis.handler import (
    FilmAnalysisHandler,
    FilmAnalysisRerunHandler,
    FilmAnalysisTools,
    YoutubeFilmAnalysisHandler,
    YoutubeFilmAnalysisTools,
)
from app.modules.jobs.film_analysis.notes_passes import WrittenNotes
from app.modules.jobs.film_analysis.prompt_passes import FilmPromptPasses, PromptPassTools
from app.modules.jobs.film_analysis.scene_detector import (
    FfmpegSceneDetector,
    SceneDetectionError,
)
from app.modules.jobs.models import (
    PROMPT_OUTPUT_KINDS,
    Job,
    JobOutputKind,
    JobStatus,
    JobStep,
    JobType,
)
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
from app.modules.jobs.video_to_markdown.transcript import Transcript, TranscriptSegment
from app.modules.jobs.video_to_markdown.whisper_transcriber import WhisperCppTranscriber
from app.modules.jobs.youtube_to_markdown.transcript_fetcher import (
    FetchedTranscript,
    YoutubeTranscriptFetcher,
)
from app.modules.jobs.youtube_to_markdown.ytdlp_downloader import YtDlpDownloader
from app.modules.providers.provider_catalog import ProviderId

JOB_ID = "job-1"
VIDEO_ID = "vfjegxHDOwI"
VIDEO_URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"
PROMPTS = {
    "videoToMarkdown": "Moments P",
    "characterImage": "Image P",
    "characterVoice": "Voice P",
    "scene": "Scene P",
}
TRANSCRIPT = Transcript(
    language="vi",
    segments=[
        TranscriptSegment(start_ms=0, end_ms=4000, text=" Chào anh."),
        TranscriptSegment(start_ms=30_000, end_ms=32_000, text=" Đi thôi."),
    ],
)
OUTLINE_REPLY = {
    "title": "Cuộc gặp",
    "summary": "Hai người gặp nhau.",
    "moments": [{"atMs": 0, "title": "Gặp gỡ"}],
}
CLAUDE_CHOICE = AiModelChoice(ProviderId.CLAUDE_CLI, "default")
GEMINI_CHOICE = AiModelChoice(ProviderId.GOOGLE, "gemini-4-argon")
MOMENT_LIMITS = AiLimits(timeout_sec=600)
PASS_LIMITS = AiLimits(timeout_sec=900)
MAX_IMAGES_BY_PROVIDER = {ProviderId.CLAUDE_CLI: 100, ProviderId.GOOGLE: 300}
MODELS_BY_GROUP = {AiStepGroup.MOMENTS: CLAUDE_CHOICE, AiStepGroup.FILM_ANALYSIS: GEMINI_CHOICE}
CHARACTERS_ANSWER = "## Character A"
FRAMES_ATTACHED_LINE = "The frames referenced in the notes are attached below"


def build_job(job_type: JobType, options: dict) -> Job:
    return Job(
        id=JOB_ID,
        type=job_type,
        status=JobStatus.PROCESSING,
        source_filename=f"Phim [{VIDEO_ID}].mp4",
        options=options,
    )


def build_upload_job() -> Job:
    return build_job(JobType.FILM_ANALYSIS, {"language": "vi", "maxFrames": 6, "prompts": PROMPTS})


def build_youtube_job() -> Job:
    return build_job(
        JobType.YOUTUBE_FILM_ANALYSIS,
        {"url": VIDEO_URL, "videoId": VIDEO_ID, "language": "auto", "prompts": PROMPTS},
    )


def build_rerun_job(**options) -> Job:
    return build_job(JobType.FILM_ANALYSIS_RERUN, {"prompts": PROMPTS, **options})


def capture_error(error_class: type[Exception], action):
    with pytest.raises(error_class) as caught:
        action()
    return caught.value


@pytest.fixture
def storage(tmp_path):
    return JobStorage(tmp_path, max_upload_bytes=1024)


@pytest.fixture
def repository():
    job_repository = MagicMock(spec=JobRepository)
    job_repository.find_outputs.return_value = {JobOutputKind.VIDEO_NOTES: "# Notes"}
    return job_repository


@pytest.fixture
def media():
    processor = MagicMock(spec=FfmpegMediaProcessor)
    processor.probe_duration_ms.return_value = 60_000
    processor.extract_audio.side_effect = lambda video_path, audio_path: audio_path
    processor.sample_frames.side_effect = write_samples
    processor.capture_frame.side_effect = write_frame
    return processor


def write_frame(video_path, at_ms, output_path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"jpeg")


def write_samples(sampling) -> None:
    for second in range(sampling.frame_count):
        (sampling.output_pattern.parent / f"sample-{second:05d}.jpg").write_bytes(b"jpeg")


@pytest.fixture
def transcriber():
    whisper = MagicMock(spec=WhisperCppTranscriber)
    whisper.transcribe.return_value = TRANSCRIPT
    return whisper


@pytest.fixture
def ai_caller():
    caller = MagicMock(spec=AiCaller)
    caller.find_model.side_effect = MODELS_BY_GROUP.get
    caller.ask_for_json.return_value = OUTLINE_REPLY
    caller.ask_for_text.side_effect = [CHARACTERS_ANSWER, "## Voice A", "## 00:00 — Shot"]
    return caller


@pytest.fixture
def scene_detector():
    detector = MagicMock(spec=FfmpegSceneDetector)
    detector.detect_cut_times_ms.return_value = [20_000, 40_000]
    return detector


@pytest.fixture
def frame_steps(storage, repository, media, ai_caller, scene_detector):
    return FilmFrameSteps(
        repository,
        FilmFrameTools(
            moment_steps=MomentPickingSteps(
                KeyMomentPicker(
                    ai_caller,
                    repository,
                    MomentPickerConfig(MOMENT_LIMITS, {ProviderId.CLAUDE_CLI: 100}),
                ),
                FrameSampler(storage, media, 512),
            ),
            scene_detector=scene_detector,
            frame_capturer=MomentFrameCapturer(storage, media),
        ),
    )


@pytest.fixture
def prompt_passes(storage, repository, ai_caller):
    return FilmPromptPasses(
        PromptPassTools(
            storage=storage,
            repository=repository,
            ai_caller=ai_caller,
            limits=PASS_LIMITS,
            max_images_by_provider=MAX_IMAGES_BY_PROVIDER,
        )
    )


@pytest.fixture
def frames_sent_in_spread_passes(storage, repository, ai_caller):
    images_dir = storage.images_dir(JOB_ID)
    images_dir.mkdir(parents=True, exist_ok=True)
    for index in range(4):
        (images_dir / f"moment-{index}.jpg").write_bytes(b"jpg")
    FilmPromptPasses(
        PromptPassTools(
            storage=storage,
            repository=repository,
            ai_caller=ai_caller,
            limits=PASS_LIMITS,
            max_images_by_provider={ProviderId.GOOGLE: 2},
        )
    ).run(build_upload_job(), WrittenNotes("# Notes", []), lambda _step: None)
    return [
        [image.label for image in call.args[1].images]
        for call in ai_caller.ask_for_text.call_args_list
    ]


@pytest.fixture
def upload_handler(storage, repository, media, transcriber, frame_steps, prompt_passes):
    return FilmAnalysisHandler(
        storage,
        repository,
        FilmAnalysisTools(
            media=media,
            transcriber=transcriber,
            frame_steps=frame_steps,
            prompt_passes=prompt_passes,
        ),
    )


@pytest.fixture
def transcript_fetcher():
    fetcher = MagicMock(spec=YoutubeTranscriptFetcher)
    fetcher.fetch.return_value = FetchedTranscript(transcript=TRANSCRIPT, duration_ms=60_000)
    return fetcher


@pytest.fixture
def downloader():
    youtube_downloader = MagicMock(spec=YtDlpDownloader)
    youtube_downloader.download_video.side_effect = lambda video_url, output_path: output_path
    return youtube_downloader


@pytest.fixture
def youtube_handler(
    storage, repository, transcript_fetcher, downloader, frame_steps, prompt_passes
):
    return YoutubeFilmAnalysisHandler(
        storage,
        repository,
        YoutubeFilmAnalysisTools(
            transcript_fetcher=transcript_fetcher,
            downloader=downloader,
            frame_steps=frame_steps,
            prompt_passes=prompt_passes,
        ),
    )


@pytest.fixture
def upload_steps(upload_handler):
    steps: list[JobStep] = []
    upload_handler.handle(build_upload_job(), steps.append)
    return steps


@pytest.fixture
def youtube_steps(youtube_handler):
    steps: list[JobStep] = []
    youtube_handler.handle(build_youtube_job(), steps.append)
    return steps


@pytest.fixture
def saved_outputs_by_kind(repository, upload_steps):
    return {call.args[1]: call.args[2] for call in repository.save_output.call_args_list}


@pytest.fixture
def youtube_video_notes(repository, youtube_steps):
    return repository.save_output.call_args_list[0].args[2]


@pytest.fixture
def writer_requests(ai_caller, upload_steps):
    return [call.args[1] for call in ai_caller.ask_for_text.call_args_list]


@pytest.fixture
def captured_positions_ms(media, upload_steps):
    return [call.args[1] for call in media.capture_frame.call_args_list]


@pytest.fixture
def picked_ask(ai_caller, upload_steps):
    return ai_caller.ask_for_json.call_args.args[1]


@pytest.fixture
def whole_video_youtube_steps(youtube_handler, downloader):
    job = build_youtube_job()
    job.options["inputMode"] = "whole_video"
    steps: list[JobStep] = []
    youtube_handler.handle(job, steps.append)
    return SimpleNamespace(steps=steps, download_count=downloader.download_video.call_count)


@pytest.fixture
def rerun_ai_calls(repository, prompt_passes, ai_caller):
    FilmAnalysisRerunHandler(repository, prompt_passes).handle(build_rerun_job(), lambda step: None)
    return SimpleNamespace(
        calls=[
            (call.args[0], call.args[1].instructions, call.args[2])
            for call in ai_caller.ask_for_text.call_args_list
        ],
        ai_used=[call.args for call in repository.save_ai_used.call_args_list],
    )


@pytest.fixture
def scene_failure(upload_handler, scene_detector):
    scene_detector.detect_cut_times_ms.side_effect = SceneDetectionError(
        "Scene detection failed: boom"
    )
    return capture_error(
        SceneDetectionError, lambda: upload_handler.handle(build_upload_job(), lambda step: None)
    )


@pytest.fixture
def no_speech_error(upload_handler, transcriber):
    transcriber.transcribe.return_value = Transcript(language="vi", segments=[])
    return capture_error(
        NoSpeechError, lambda: upload_handler.handle(build_upload_job(), lambda step: None)
    )


@pytest.fixture
def voice_pass_failure(upload_handler, ai_caller):
    ai_caller.ask_for_text.side_effect = [CHARACTERS_ANSWER, AiCallError("gemini failed: x")]
    return capture_error(
        AiCallError, lambda: upload_handler.handle(build_upload_job(), lambda step: None)
    )


@pytest.fixture
def output_kinds_saved_before_failure(repository, voice_pass_failure):
    return [call.args[1] for call in repository.save_output.call_args_list]


@pytest.fixture
def rerun_steps(repository, prompt_passes):
    steps: list[JobStep] = []
    FilmAnalysisRerunHandler(repository, prompt_passes).handle(build_rerun_job(), steps.append)
    return steps


@pytest.fixture
def rerun_without_notes_error(repository, prompt_passes):
    repository.find_outputs.return_value = {}
    handler = FilmAnalysisRerunHandler(repository, prompt_passes)
    return capture_error(
        NoVideoNotesError, lambda: handler.handle(build_rerun_job(), lambda step: None)
    )


def test_upload_handler_reports_every_step_in_order(upload_steps):
    assert upload_steps == [
        JobStep.EXTRACTING_AUDIO,
        JobStep.TRANSCRIBING,
        JobStep.PICKING_MOMENTS,
        JobStep.DETECTING_SCENES,
        JobStep.CAPTURING_FRAMES,
        JobStep.WRITING_MARKDOWN,
        JobStep.WRITING_CHARACTER_IMAGE_PROMPTS,
        JobStep.WRITING_CHARACTER_VOICE_PROMPTS,
        JobStep.WRITING_SCENE_PROMPTS,
    ]


def test_upload_handler_clears_outputs_of_an_earlier_run(repository, upload_steps):
    repository.delete_outputs.assert_called_once_with(JOB_ID, tuple(JobOutputKind))


def test_upload_handler_gives_half_the_frames_to_dialogue(picked_ask):
    assert (picked_ask.instructions, "at most 3 key moments" in picked_ask.message) == (
        "Moments P",
        True,
    )


def test_youtube_handler_in_whole_video_mode_downloads_once_before_picking(
    whole_video_youtube_steps,
):
    assert whole_video_youtube_steps.steps[:5] == [
        JobStep.FETCHING_TRANSCRIPT,
        JobStep.DOWNLOADING_VIDEO,
        JobStep.SAMPLING_FRAMES,
        JobStep.PICKING_MOMENTS,
        JobStep.DETECTING_SCENES,
    ]
    assert whole_video_youtube_steps.download_count == 1


def test_each_pass_records_then_uses_the_film_analysis_model(rerun_ai_calls):
    assert rerun_ai_calls.calls == [
        (GEMINI_CHOICE, "Image P", PASS_LIMITS),
        (GEMINI_CHOICE, "Voice P", PASS_LIMITS),
        (GEMINI_CHOICE, "Scene P", PASS_LIMITS),
    ]
    assert rerun_ai_calls.ai_used == [
        (JOB_ID, JobStep.WRITING_CHARACTER_IMAGE_PROMPTS, GEMINI_CHOICE),
        (JOB_ID, JobStep.WRITING_CHARACTER_VOICE_PROMPTS, GEMINI_CHOICE),
        (JOB_ID, JobStep.WRITING_SCENE_PROMPTS, GEMINI_CHOICE),
    ]


def test_upload_handler_captures_dialogue_and_scene_frames(captured_positions_ms):
    assert captured_positions_ms == [0, 20_000, 40_000]


def test_upload_handler_saves_frame_counts(repository, upload_steps):
    repository.merge_options.assert_called_once_with(
        JOB_ID, {"frameCounts": {"dialogue": 1, "scene": 2}}
    )


def test_upload_handler_stores_every_output_without_a_markdown_file(saved_outputs_by_kind, storage):
    assert list(saved_outputs_by_kind) == [
        JobOutputKind.VIDEO_NOTES,
        JobOutputKind.CHARACTER_IMAGE_PROMPTS,
        JobOutputKind.CHARACTER_VOICE_PROMPTS,
        JobOutputKind.SCENE_PROMPTS,
    ]
    assert "## 00:20 — Scene change" in saved_outputs_by_kind[JobOutputKind.VIDEO_NOTES]
    assert not storage.archive_path(JOB_ID).exists()


def test_image_pass_reads_notes_and_frames_without_characters(writer_requests, storage):
    assert writer_requests[0].instructions == "Image P"
    assert writer_requests[0].message.startswith("Video notes:\n\n# Cuộc gặp")
    assert FRAMES_ATTACHED_LINE in writer_requests[0].message
    assert "Characters:" not in writer_requests[0].message
    assert {image.path.parent for image in writer_requests[0].images} == {
        storage.images_dir(JOB_ID)
    }


def test_each_pass_sends_at_most_the_call_limit_of_frames_spread_evenly(
    frames_sent_in_spread_passes,
):
    assert frames_sent_in_spread_passes == [["images/moment-0.jpg", "images/moment-2.jpg"]] * 3


def test_voice_and_scene_passes_also_read_the_character_answer(writer_requests):
    assert [request.instructions for request in writer_requests[1:]] == ["Voice P", "Scene P"]
    assert f"Characters:\n\n{CHARACTERS_ANSWER}" in writer_requests[1].message
    assert writer_requests[1].message == writer_requests[2].message


def test_youtube_handler_reports_every_step_in_order(youtube_steps):
    assert youtube_steps == [
        JobStep.FETCHING_TRANSCRIPT,
        JobStep.PICKING_MOMENTS,
        JobStep.DOWNLOADING_VIDEO,
        JobStep.DETECTING_SCENES,
        JobStep.CAPTURING_FRAMES,
        JobStep.WRITING_MARKDOWN,
        JobStep.WRITING_CHARACTER_IMAGE_PROMPTS,
        JobStep.WRITING_CHARACTER_VOICE_PROMPTS,
        JobStep.WRITING_SCENE_PROMPTS,
    ]


def test_youtube_handler_links_notes_headings_to_youtube(youtube_video_notes):
    assert f"## [00:20]({VIDEO_URL}&t=20s) — Scene change" in youtube_video_notes


def test_youtube_handler_detects_scenes_in_the_downloaded_video(
    scene_detector, storage, youtube_steps
):
    scene_detector.detect_cut_times_ms.assert_called_once_with(
        storage.source_path(JOB_ID, f"Phim [{VIDEO_ID}].mp4")
    )


def test_upload_handler_fails_a_film_without_speech(no_speech_error, ai_caller):
    assert str(no_speech_error) == "No speech was detected in the video"
    ai_caller.ask_for_json.assert_not_called()


def test_a_scene_detection_failure_stops_before_capturing(scene_failure, media, repository):
    assert str(scene_failure) == "Scene detection failed: boom"
    media.capture_frame.assert_not_called()
    repository.save_output.assert_not_called()


def test_a_failing_pass_keeps_the_outputs_written_before_it(output_kinds_saved_before_failure):
    assert output_kinds_saved_before_failure == [
        JobOutputKind.VIDEO_NOTES,
        JobOutputKind.CHARACTER_IMAGE_PROMPTS,
    ]


def test_rerun_handler_runs_only_the_prompt_passes(rerun_steps, repository):
    assert rerun_steps == [
        JobStep.WRITING_CHARACTER_IMAGE_PROMPTS,
        JobStep.WRITING_CHARACTER_VOICE_PROMPTS,
        JobStep.WRITING_SCENE_PROMPTS,
    ]
    repository.delete_outputs.assert_called_once_with(JOB_ID, PROMPT_OUTPUT_KINDS)


def test_rerun_handler_fails_without_video_notes(rerun_without_notes_error, ai_caller):
    assert str(rerun_without_notes_error) == f"Job {JOB_ID} has no video notes to reuse"
    ai_caller.ask_for_text.assert_not_called()
