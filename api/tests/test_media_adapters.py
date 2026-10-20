import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.common.process import CommandError, CommandRunner
from app.modules.jobs.video_to_markdown.ffmpeg_media import (
    AudioSplit,
    FfmpegConfig,
    FfmpegMediaProcessor,
    FrameSampling,
    VideoCompression,
)
from app.modules.jobs.video_to_markdown.transcript import Transcript, TranscriptSegment
from app.modules.jobs.video_to_markdown.whisper_transcriber import (
    WhisperConfig,
    WhisperCppTranscriber,
)

VIDEO_PATH = Path("/videos/clip.mp4")
WHISPER_OUTPUT = {
    "result": {"language": "ja"},
    "transcription": [{"offsets": {"from": 0, "to": 900}, "text": "こんにちは"}],
}


def write_whisper_output(command) -> str:
    output_base = Path(command.args[command.args.index("-of") + 1])
    output_base.with_suffix(".json").write_text(json.dumps(WHISPER_OUTPUT), encoding="utf-8")
    return ""


@pytest.fixture
def runner():
    return MagicMock(spec=CommandRunner)


@pytest.fixture
def media(runner):
    return FfmpegMediaProcessor(FfmpegConfig("ffmpeg", "ffprobe", 60), runner)


@pytest.fixture
def probed_duration_ms(runner, media):
    runner.run.return_value = "12.3456\n"
    return media.probe_duration_ms(VIDEO_PATH)


@pytest.fixture
def unknown_duration_error(runner, media):
    runner.run.return_value = "N/A\n"
    with pytest.raises(CommandError) as caught:
        media.probe_duration_ms(VIDEO_PATH)
    return caught.value


@pytest.fixture
def audio_command_args(runner, media):
    media.extract_audio(VIDEO_PATH, Path("/work/audio.wav"))
    return runner.run.call_args.args[0].args


@pytest.fixture
def frame_command_args(runner, media):
    media.capture_frame(VIDEO_PATH, 83_250, Path("/out/frame.jpg"))
    return runner.run.call_args.args[0].args


@pytest.fixture
def sampling_command(runner, media):
    media.sample_frames(
        FrameSampling(
            video_path=VIDEO_PATH,
            output_pattern=Path("/jobs/j1/samples/sample-%05d.jpg"),
            frame_count=12,
            max_width_px=512,
        )
    )
    return runner.run.call_args.args[0]


@pytest.fixture
def audio_split_command(runner, media):
    media.split_audio(
        AudioSplit(video_path=VIDEO_PATH, output_dir=Path("/jobs/j1/audio"), part_sec=1800)
    )
    return runner.run.call_args.args[0]


@pytest.fixture
def compression_command(runner, media):
    media.compress_video(
        VideoCompression(
            video_path=VIDEO_PATH,
            output_dir=Path("/jobs/j1/compressed"),
            part_sec=1800,
            max_side_px=480,
            max_fps=24,
        )
    )
    return runner.run.call_args.args[0]


@pytest.fixture
def model_path(tmp_path):
    model_file = tmp_path / "model.bin"
    model_file.write_bytes(b"model")
    return model_file


@pytest.fixture
def transcript(runner, model_path, tmp_path):
    runner.run.side_effect = write_whisper_output
    transcriber = WhisperCppTranscriber(WhisperConfig("whisper-cli", model_path, 60), runner)
    return transcriber.transcribe(tmp_path / "audio.wav", "auto")


@pytest.fixture
def missing_model_error(runner, tmp_path):
    transcriber = WhisperCppTranscriber(
        WhisperConfig("whisper-cli", tmp_path / "absent.bin", 60), runner
    )
    with pytest.raises(CommandError) as caught:
        transcriber.transcribe(tmp_path / "audio.wav", "auto")
    return caught.value


def test_probe_duration_ms_converts_seconds_to_milliseconds(probed_duration_ms):
    assert probed_duration_ms == 12_345


def test_probe_duration_ms_raises_when_duration_is_unknown(unknown_duration_error):
    assert "no duration for clip.mp4" in str(unknown_duration_error)


def test_extract_audio_writes_16khz_mono_wav(audio_command_args):
    assert audio_command_args[-8:] == [
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        "/work/audio.wav",
    ]


def test_capture_frame_seeks_to_the_moment(frame_command_args):
    assert frame_command_args[4:8] == ["-ss", "83.250", "-i", "/videos/clip.mp4"]


def test_sample_frames_takes_one_frame_per_second_in_one_pass(sampling_command):
    assert sampling_command.args == [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        "/videos/clip.mp4",
        "-vf",
        "fps=1,scale='min(512,iw)':-2",
        "-frames:v",
        "12",
        "-q:v",
        "3",
        "-start_number",
        "0",
        "/jobs/j1/samples/sample-%05d.jpg",
    ]
    assert sampling_command.timeout_sec == 60


def test_transcribe_reads_whisper_json_output(transcript):
    assert transcript == Transcript(
        language="ja", segments=[TranscriptSegment(start_ms=0, end_ms=900, text="こんにちは")]
    )


def test_transcribe_raises_when_model_is_missing(missing_model_error, runner):
    assert "Whisper model not found" in str(missing_model_error)
    runner.run.assert_not_called()


def test_split_audio_writes_mono_aac_parts_in_one_pass(audio_split_command):
    assert audio_split_command.args == [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        "/videos/clip.mp4",
        "-vn",
        "-ac",
        "1",
        "-c:a",
        "aac",
        "-b:a",
        "64k",
        "-f",
        "segment",
        "-segment_time",
        "1800",
        "-reset_timestamps",
        "1",
        "-segment_start_number",
        "1",
        "/jobs/j1/audio/part-%02d.m4a",
    ]
    assert audio_split_command.timeout_sec == 60


def test_compress_video_caps_the_long_side_and_frame_rate_and_cuts_parts(compression_command):
    assert compression_command.args == [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        "/videos/clip.mp4",
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-vf",
        "scale='if(gte(iw,ih),trunc(min(480,iw)/2)*2,-2)':"
        "'if(gte(iw,ih),-2,trunc(min(480,ih)/2)*2)'",
        "-fpsmax",
        "24",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "28",
        "-pix_fmt",
        "yuv420p",
        "-force_key_frames",
        "expr:gte(t,n_forced*1800)",
        "-c:a",
        "aac",
        "-ac",
        "1",
        "-b:a",
        "64k",
        "-f",
        "segment",
        "-segment_time",
        "1800",
        "-reset_timestamps",
        "1",
        "-segment_start_number",
        "1",
        "/jobs/j1/compressed/part-%02d.mp4",
    ]
    assert compression_command.timeout_sec == 60
