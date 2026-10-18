from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.common.process import CommandError
from app.modules.ai_models.ai_caller import AiCaller
from app.modules.ai_models.ai_calls import AiCallError, AiLimits, AiModelChoice, AiStepGroup
from app.modules.jobs.models import Job, JobStep
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.storage import JobStorage
from app.modules.jobs.video_to_markdown.ffmpeg_media import FfmpegMediaProcessor
from app.modules.jobs.video_to_markdown.frame_sampler import (
    FrameSampler,
    FrameSamplingError,
    to_sample_count,
)
from app.modules.jobs.video_to_markdown.moment_steps import (
    KeyMomentPicker,
    MomentPickerConfig,
    MomentPickingSteps,
    MomentSource,
    OutlineRequest,
)
from app.modules.jobs.video_to_markdown.moment_windows import (
    MomentWindow,
    SampleFrame,
    WindowPlan,
    split_into_windows,
    to_window_max_moments,
)
from app.modules.jobs.video_to_markdown.moments import KeyMoment, VideoOutline
from app.modules.jobs.video_to_markdown.outline_reply import (
    OUTLINE_SCHEMA,
    MomentPickerError,
    reply_to_outline,
)
from app.modules.jobs.video_to_markdown.transcript import TranscriptSegment
from app.modules.providers.provider_catalog import ProviderId

JOB_ID = "job-1"
VIDEO_PATH = Path("/videos/source.mp4")
SEGMENTS = [
    TranscriptSegment(start_ms=500, end_ms=2000, text=" Hello."),
    TranscriptSegment(start_ms=2500, end_ms=4000, text=" Open the box."),
    TranscriptSegment(start_ms=5200, end_ms=6000, text=" Done."),
]
CLAUDE_CHOICE = AiModelChoice(ProviderId.CLAUDE_CLI, "default")
GEMINI_CHOICE = AiModelChoice(ProviderId.GOOGLE, "gemini-4-argon")
OPENAI_CHOICE = AiModelChoice(ProviderId.OPENAI, "gpt-6-astra")
LIMITS = AiLimits(timeout_sec=600)
PICKER_CONFIG = MomentPickerConfig(
    limits=LIMITS,
    max_images_by_provider={
        ProviderId.CLAUDE_CLI: 100,
        ProviderId.GOOGLE: 3,
        ProviderId.OPENAI: 300,
    },
)
WINDOW_REPLIES = [
    {
        "title": "First part",
        "summary": "Opening.",
        "moments": [{"atMs": 500, "title": "Hello"}, {"atMs": 1000, "title": "Too close"}],
    },
    {
        "title": "Second part",
        "summary": "Ending.",
        "moments": [{"atMs": 9000, "title": "Beyond the end"}, {"atMs": 4000, "title": " "}],
    },
]


def build_samples(count: int) -> list[SampleFrame]:
    return [
        SampleFrame(at_ms=second * 1000, path=Path(f"/s/sample-{second:05d}.jpg"))
        for second in range(count)
    ]


def build_plan(**values) -> WindowPlan:
    defaults = {
        "segments": SEGMENTS,
        "samples": build_samples(6),
        "duration_ms": 6400,
        "max_moments": 4,
        "max_images": 3,
    }
    return WindowPlan(**{**defaults, **values})


def build_request(**values) -> OutlineRequest:
    defaults = {
        "segments": SEGMENTS,
        "duration_ms": 6400,
        "max_moments": 4,
        "instructions": "Pick moments",
    }
    return OutlineRequest(job_id=JOB_ID, **{**defaults, **values})


def build_picker(choice: AiModelChoice, replies):
    ai_caller = MagicMock(spec=AiCaller)
    ai_caller.find_model.return_value = choice
    ai_caller.ask_for_json.side_effect = replies
    repository = MagicMock(spec=JobRepository)
    return SimpleNamespace(
        picker=KeyMomentPicker(ai_caller, repository, PICKER_CONFIG),
        ai_caller=ai_caller,
        repository=repository,
    )


def write_samples(sampling) -> None:
    for second in range(sampling.frame_count):
        (sampling.output_pattern.parent / f"sample-{second:05d}.jpg").write_bytes(b"jpeg")


@pytest.fixture
def storage(tmp_path):
    return JobStorage(tmp_path, max_upload_bytes=1024)


@pytest.fixture
def media():
    processor = MagicMock(spec=FfmpegMediaProcessor)
    processor.sample_frames.side_effect = write_samples
    return processor


@pytest.fixture
def two_windows():
    return split_into_windows(build_plan())


@pytest.fixture
def last_window_of_long_captions():
    late_segment = TranscriptSegment(start_ms=9000, end_ms=9500, text=" After the frames.")
    return split_into_windows(build_plan(segments=[*SEGMENTS, late_segment]))[-1]


@pytest.fixture(
    params=[
        (4, 3000, 6400, 2),
        (4, 400, 6400, 1),
        (12, 0, 0, 1),
    ]
)
def window_max_moments(request):
    max_moments, window_ms, duration_ms, expected = request.param
    plan = build_plan(max_moments=max_moments, duration_ms=duration_ms)
    return SimpleNamespace(actual=to_window_max_moments(plan, window_ms), expected=expected)


@pytest.fixture(params=[(0, 0), (499, 0), (500, 1), (1499, 1), (1500, 2), (670_000, 670)])
def sample_count(request):
    duration_ms, expected = request.param
    return SimpleNamespace(actual=to_sample_count(duration_ms), expected=expected)


@pytest.fixture
def sampled(storage, media):
    stale_sample = storage.samples_dir(JOB_ID) / "sample-00099.jpg"
    stale_sample.parent.mkdir(parents=True)
    stale_sample.write_bytes(b"old")
    samples = FrameSampler(storage, media, 512).sample(JOB_ID, VIDEO_PATH, 3400)
    return SimpleNamespace(samples=samples, sampling=media.sample_frames.call_args.args[0])


@pytest.fixture
def too_short_sampling(storage, media):
    samples = FrameSampler(storage, media, 512).sample(JOB_ID, VIDEO_PATH, 400)
    return SimpleNamespace(samples=samples, media=media)


@pytest.fixture
def sampling_error(storage, media):
    media.sample_frames.side_effect = CommandError("ffmpeg timed out after 1800s")
    with pytest.raises(FrameSamplingError) as caught:
        FrameSampler(storage, media, 512).sample(JOB_ID, VIDEO_PATH, 3400)
    return caught.value


@pytest.fixture
def picked_from_samples():
    rig = build_picker(GEMINI_CHOICE, WINDOW_REPLIES)
    outline = rig.picker.pick_from_samples(build_request(), build_samples(6))
    calls = rig.ai_caller.ask_for_json.call_args_list
    return SimpleNamespace(
        outline=outline,
        asks=[call.args[1] for call in calls],
        choices_and_limits=[(call.args[0], call.args[2]) for call in calls],
        rig=rig,
    )


@pytest.fixture
def silent_window_message():
    rig = build_picker(GEMINI_CHOICE, WINDOW_REPLIES)
    rig.picker.pick_from_samples(build_request(segments=[]), build_samples(6))
    return rig.ai_caller.ask_for_json.call_args.args[1].message


@pytest.fixture
def claude_window_asks():
    rig = build_picker(CLAUDE_CHOICE, WINDOW_REPLIES)
    rig.picker.pick_from_samples(build_request(), build_samples(6))
    return [call.args[1] for call in rig.ai_caller.ask_for_json.call_args_list]


@pytest.fixture
def transcript_pick():
    rig = build_picker(
        CLAUDE_CHOICE,
        [{"title": "T", "summary": "S", "moments": [{"atMs": 7000, "title": "Late"}]}],
    )
    outline = rig.picker.pick_from_transcript(build_request())
    return SimpleNamespace(
        outline=outline, ask=rig.ai_caller.ask_for_json.call_args.args[1], rig=rig
    )


@pytest.fixture
def malformed_openai_moment():
    rig = build_picker(OPENAI_CHOICE, [{"moments": [{"atMs": "x", "title": "t"}]}])
    with pytest.raises(MomentPickerError) as caught:
        rig.picker.pick_from_transcript(build_request())
    return str(caught.value)


def build_steps_rig(storage, media, ai_caller):
    steps = MomentPickingSteps(
        KeyMomentPicker(ai_caller, MagicMock(spec=JobRepository), PICKER_CONFIG),
        FrameSampler(storage, media, 512),
    )
    events: list = []
    source = MomentSource(
        job=Job(id=JOB_ID, options={"inputMode": "whole_video"}),
        segments=SEGMENTS,
        duration_ms=6400,
        get_video_path=lambda: events.append("video") or VIDEO_PATH,
    )
    return SimpleNamespace(steps=steps, source=source, events=events)


@pytest.fixture
def subtitles_run(storage, media):
    ai_caller = MagicMock(spec=AiCaller)
    ai_caller.find_model.return_value = CLAUDE_CHOICE
    rig = build_steps_rig(storage, media, ai_caller)
    ai_caller.ask_for_json.side_effect = lambda choice, ask, limits: (
        rig.events.append("pick") or {"title": "T", "summary": "S", "moments": []}
    )
    source = MomentSource(
        job=Job(id=JOB_ID, options={}),
        segments=SEGMENTS,
        duration_ms=6400,
        get_video_path=rig.source.get_video_path,
    )
    picked = rig.steps.pick(source, 4, rig.events.append)
    return SimpleNamespace(picked=picked, events=rig.events, media=media)


@pytest.fixture
def failed_window_run(storage, media):
    ai_caller = MagicMock(spec=AiCaller)
    ai_caller.find_model.return_value = CLAUDE_CHOICE
    ai_caller.ask_for_json.side_effect = AiCallError("claude failed: Overloaded")
    rig = build_steps_rig(storage, media, ai_caller)
    with pytest.raises(AiCallError) as caught:
        rig.steps.pick(rig.source, 4, rig.events.append)
    return SimpleNamespace(error=caught.value, events=rig.events)


@pytest.fixture
def malformed_gemini_moment():
    with pytest.raises(MomentPickerError) as caught:
        reply_to_outline({"moments": [{"title": "no time"}]}, "gemini")
    return str(caught.value)


def test_samples_split_into_windows_of_the_image_limit(two_windows):
    assert [(window.start_ms, window.end_ms, window.max_moments) for window in two_windows] == [
        (0, 3000, 2),
        (3000, 6000, 2),
    ]
    assert [[sample.at_ms for sample in window.samples] for window in two_windows] == [
        [0, 1000, 2000],
        [3000, 4000, 5000],
    ]


def test_each_window_holds_the_lines_that_start_in_it(two_windows):
    assert [[segment.start_ms for segment in window.segments] for window in two_windows] == [
        [500, 2500],
        [5200],
    ]


def test_the_last_window_ends_at_the_duration_and_keeps_later_lines(
    last_window_of_long_captions,
):
    assert last_window_of_long_captions.end_ms == 6000
    assert [segment.start_ms for segment in last_window_of_long_captions.segments] == [
        5200,
        9000,
    ]


def test_a_video_without_samples_still_gets_one_window():
    assert split_into_windows(build_plan(samples=[], duration_ms=300)) == [
        MomentWindow(start_ms=0, end_ms=300, max_moments=4, segments=SEGMENTS, samples=[])
    ]


def test_a_window_asks_for_its_share_of_the_moments(window_max_moments):
    assert window_max_moments.actual == window_max_moments.expected


def test_sample_count_stops_half_a_second_before_the_end(sample_count):
    assert sample_count.actual == sample_count.expected


def test_sampler_empties_the_folder_and_names_samples_by_second(sampled, storage):
    assert [(sample.at_ms, sample.path.name) for sample in sampled.samples] == [
        (0, "sample-00000.jpg"),
        (1000, "sample-00001.jpg"),
        (2000, "sample-00002.jpg"),
    ]
    assert sampled.sampling.output_pattern == storage.samples_dir(JOB_ID) / "sample-%05d.jpg"
    assert (sampled.sampling.frame_count, sampled.sampling.max_width_px) == (3, 512)


def test_sampler_skips_ffmpeg_for_a_video_under_half_a_second(too_short_sampling):
    assert too_short_sampling.samples == []
    too_short_sampling.media.sample_frames.assert_not_called()


def test_sampler_reports_an_ffmpeg_failure(sampling_error):
    assert str(sampling_error) == "Frame sampling failed: ffmpeg timed out after 1800s"


def test_the_model_is_read_once_and_recorded_when_picking_starts(picked_from_samples):
    picked_from_samples.rig.ai_caller.find_model.assert_called_once_with(AiStepGroup.MOMENTS)
    picked_from_samples.rig.repository.save_ai_used.assert_called_once_with(
        JOB_ID, JobStep.PICKING_MOMENTS, GEMINI_CHOICE
    )
    assert picked_from_samples.choices_and_limits == [(GEMINI_CHOICE, LIMITS)] * 2


def test_windows_are_asked_in_time_order_with_their_frames(picked_from_samples):
    first_ask, second_ask = picked_from_samples.asks
    assert (first_ask.instructions, first_ask.reply_schema) == ("Pick moments", OUTLINE_SCHEMA)
    assert first_ask.message == (
        "This part of the video runs from 00:00 to 00:03. Choose at most 2 key moments in it. "
        "Set atMs to the time of the frame or the line where the moment begins.\n\n"
        "Transcript:\n[500ms] Hello.\n[2500ms] Open the box.\n\nFrames:"
    )
    assert [image.label for image in first_ask.images] == ["[0ms]", "[1000ms]", "[2000ms]"]
    assert [image.label for image in second_ask.images] == ["[3000ms]", "[4000ms]", "[5000ms]"]


def test_a_window_without_lines_says_so(silent_window_message):
    assert "Transcript:\n(no speech in this part)\n\nFrames:" in silent_window_message


def test_merged_moments_take_the_first_window_title_and_are_normalised(picked_from_samples):
    assert picked_from_samples.outline == VideoOutline(
        title="First part",
        summary="Opening.",
        moments=[KeyMoment(500, "Hello"), KeyMoment(5900, "Beyond the end")],
    )


def test_the_window_size_is_the_image_limit_of_the_model_provider(claude_window_asks):
    assert [len(ask.images) for ask in claude_window_asks] == [6]


def test_transcript_picking_asks_once_without_images_and_normalises(transcript_pick):
    assert transcript_pick.outline == VideoOutline("T", "S", [KeyMoment(5900, "Late")])
    assert (transcript_pick.ask.images, transcript_pick.ask.reply_schema) == ((), OUTLINE_SCHEMA)
    assert transcript_pick.ask.message.endswith(
        "[500ms] Hello.\n[2500ms] Open the box.\n[5200ms] Done."
    )
    transcript_pick.rig.repository.save_ai_used.assert_called_once_with(
        JOB_ID, JobStep.PICKING_MOMENTS, CLAUDE_CHOICE
    )


def test_a_malformed_moment_names_the_ai_that_answered(malformed_openai_moment):
    assert malformed_openai_moment == (
        "openai returned a malformed moment: invalid literal for int() with base 10: 'x'"
    )


def test_subtitles_mode_picks_before_it_needs_the_video(subtitles_run):
    assert subtitles_run.events == [JobStep.PICKING_MOMENTS, "pick", "video"]
    assert subtitles_run.picked.video_path == VIDEO_PATH
    subtitles_run.media.sample_frames.assert_not_called()


def test_a_failing_window_fails_the_step_and_deletes_the_samples(failed_window_run, storage):
    assert str(failed_window_run.error) == "claude failed: Overloaded"
    assert failed_window_run.events == ["video", JobStep.SAMPLING_FRAMES, JobStep.PICKING_MOMENTS]
    assert not storage.samples_dir(JOB_ID).exists()


def test_a_malformed_moment_names_the_model(malformed_gemini_moment):
    assert malformed_gemini_moment == "gemini returned a malformed moment: 'atMs'"
