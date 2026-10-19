import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.common.process import Command, CommandError, CommandRunner
from app.modules.films.errors import (
    EpisodeNotFoundError,
    EpisodeStepFailedError,
    FilmProjectNotFoundError,
)
from app.modules.films.ffmpeg_assembler import (
    AssemblerConfig,
    AssemblerTools,
    FfmpegEpisodeAssembler,
)
from app.modules.films.film_files import FilmFiles
from app.modules.films.models import (
    Episode,
    EpisodePart,
    FilmProject,
    MediaStatus,
    Orientation,
    Scene,
    SubtitleStyle,
)
from app.modules.films.repository import FilmRepository
from app.modules.films.stage_runner import AssembledFilm

FFMPEG_BIN = "ffmpeg-test"
FFPROBE_BIN = "ffprobe-test"
UPLOAD_MAX_MB = 20
EPISODE_DIR = "projects/p1/episodes/e1"
OUTPUT_DIR = f"{EPISODE_DIR}/output"
STEM = "Test Series - E02 - Race Against Time"
JOINED_KEY = "joined.mp4"
SRT_TEXT = (
    "1\n00:00:00,000 --> 00:00:03,200\nThe fog rolls in.\n"
    "\n"
    "2\n00:00:03,700 --> 00:00:10,700\nThe bell rings under the water.\n"
)


def to_report(duration_s: str, codec_types: list[str]) -> str:
    return json.dumps(
        {
            "streams": [{"codec_type": codec_type} for codec_type in codec_types],
            "format": {"duration": duration_s},
        }
    )


SOUND_CLIP_REPORT = to_report("8.000000", ["video", "audio"])
SILENT_CLIP_REPORT = to_report("8.000000", ["video"])
TC33_REPORTS = {
    "s1/clip.mp4": SOUND_CLIP_REPORT,
    "s1/narration.wav": to_report("3.200000", ["audio"]),
    "s2/clip.mp4": SILENT_CLIP_REPORT,
    "s2/narration.wav": to_report("8.000000", ["audio"]),
    "s3/clip.mp4": SOUND_CLIP_REPORT,
    JOINED_KEY: to_report("17.708333", ["video", "audio"]),
}


def report_key(media_path: Path) -> str:
    if media_path.name == JOINED_KEY:
        return JOINED_KEY
    return f"{media_path.parent.name}/{media_path.name}"


@dataclass
class FakeMedia:
    reports_by_key: dict[str, str]
    clock: SimpleNamespace
    ffmpeg_error: CommandError | None = None
    ffmpeg_seconds: float = 0.0
    probe_seconds: float = 0.0
    commands: list[Command] = field(default_factory=list)
    work_dir_listings: list[list[str]] = field(default_factory=list)

    def run(self, command: Command) -> str:
        self.commands.append(command)
        if command.program == FFPROBE_BIN:
            self.clock.now += self.probe_seconds
            return self.reports_by_key[report_key(Path(command.args[-1]))]
        self.clock.now += self.ffmpeg_seconds
        if self.ffmpeg_error is not None:
            raise self.ffmpeg_error
        self.work_dir_listings.append(sorted(path.name for path in command.cwd.iterdir()))
        Path(command.args[-1]).write_bytes(b"media")
        return ""


def build_project(**values) -> FilmProject:
    defaults = {
        "id": "p1",
        "name": "Test Series",
        "orientation": Orientation.LANDSCAPE,
        "allow_narration": True,
        "allow_music": False,
        "clip_duration_s": 8,
    }
    return FilmProject(**{**defaults, **values})


def build_episode(**values) -> Episode:
    defaults = {
        "id": "e1",
        "project_id": "p1",
        "number": 2,
        "title": "Race Against Time",
        "burn_subtitles": False,
        "subtitle_style": SubtitleStyle.CLEAN_WHITE,
        "music_status": MediaStatus.NONE,
        "music_path": None,
        "video_path": None,
        "subtitles_path": None,
    }
    return Episode(**{**defaults, **values})


def build_part(number: int) -> EpisodePart:
    return EpisodePart(id=f"pt{number}", episode_id="e1", position=number - 1)


def build_scene(number: int, **values) -> Scene:
    defaults = {
        "id": f"s{number}",
        "part_id": "pt1",
        "position": number - 1,
        "clip_status": MediaStatus.DONE,
        "clip_path": f"{EPISODE_DIR}/scenes/s{number}/clip.mp4",
        "narration_status": MediaStatus.NONE,
        "narration_path": None,
        "narrator_text": None,
        "trim_start_ms": 1000,
        "trim_end_ms": None,
    }
    return Scene(**{**defaults, **values})


def narrated(number: int, text: str) -> dict:
    return {
        "narration_status": MediaStatus.DONE,
        "narration_path": f"{EPISODE_DIR}/scenes/s{number}/narration.wav",
        "narrator_text": text,
    }


def tc33_scenes() -> list[Scene]:
    return [
        build_scene(1, **narrated(1, "The fog rolls in.")),
        build_scene(2, **narrated(2, "The bell rings under the water.")),
        build_scene(3),
    ]


@dataclass(frozen=True)
class Scenario:
    project: FilmProject | None
    episode: Episode | None
    scenes: list[Scene]
    media: FakeMedia
    timeout_sec: int = 3600
    parts: list[EpisodePart] = field(default_factory=lambda: [build_part(1)])


def build_media(reports_by_key: dict[str, str], **values) -> FakeMedia:
    return FakeMedia(reports_by_key=reports_by_key, clock=SimpleNamespace(now=0.0), **values)


def write_file(path: Path, content: str = "old") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def run_assembly(tmp_path: Path, scenario: Scenario) -> SimpleNamespace:
    repository = MagicMock(spec=FilmRepository)
    repository.find_episode.return_value = scenario.episode
    repository.find_project.return_value = scenario.project
    repository.find_parts.return_value = scenario.parts
    repository.find_scenes.return_value = scenario.scenes
    runner = MagicMock(spec=CommandRunner)
    runner.run.side_effect = scenario.media.run
    files = FilmFiles(tmp_path / "storage", UPLOAD_MAX_MB)
    assembler = FfmpegEpisodeAssembler(
        AssemblerConfig(
            ffmpeg_bin=FFMPEG_BIN,
            ffprobe_bin=FFPROBE_BIN,
            timeout_sec=scenario.timeout_sec,
            music_volume=0.2,
            work_root=tmp_path / "work",
        ),
        AssemblerTools(
            repository=repository,
            files=files,
            runner=runner,
            clock=lambda: scenario.media.clock.now,
        ),
    )
    return SimpleNamespace(assembler=assembler, files=files, work_root=tmp_path / "work")


def summarize_commands(media: FakeMedia) -> SimpleNamespace:
    ffmpeg_commands = [command for command in media.commands if command.program == FFMPEG_BIN]
    return SimpleNamespace(
        probed_keys=[
            report_key(Path(command.args[-1]))
            for command in media.commands
            if command.program == FFPROBE_BIN
        ],
        ffmpeg_outputs=[Path(command.args[-1]).name for command in ffmpeg_commands],
        scene_lengths=[
            command.args[command.args.index("-t") + 1] for command in ffmpeg_commands[:-2]
        ],
        concat_args=ffmpeg_commands[-2].args,
        finish_args=ffmpeg_commands[-1].args,
        work_dir=ffmpeg_commands[-1].cwd,
        timeouts_sec={command.timeout_sec for command in media.commands},
        folders={command.cwd for command in media.commands},
    )


def failed_message(tmp_path: Path, scenario: Scenario) -> SimpleNamespace:
    run = run_assembly(tmp_path, scenario)
    with pytest.raises(EpisodeStepFailedError) as error_info:
        run.assembler.assemble("e1")
    return SimpleNamespace(
        message=str(error_info.value),
        leftover_work=sorted(run.work_root.glob("*")),
        command_count=len(scenario.media.commands),
        output_files=sorted(run.files.output_dir("p1", "e1").glob("*")),
    )


@pytest.fixture
def assembled(tmp_path):
    scenario = Scenario(
        project=build_project(),
        episode=build_episode(
            video_path=f"{OUTPUT_DIR}/Old Title.mp4",
            subtitles_path=f"{OUTPUT_DIR}/{STEM}.srt",
        ),
        scenes=tc33_scenes(),
        media=build_media(TC33_REPORTS),
    )
    run = run_assembly(tmp_path, scenario)
    old_video = write_file(run.files.to_absolute(f"{OUTPUT_DIR}/Old Title.mp4"))
    write_file(run.files.to_absolute(f"{OUTPUT_DIR}/{STEM}.srt"))
    result = run.assembler.assemble("e1")
    return SimpleNamespace(
        result=result,
        commands=summarize_commands(scenario.media),
        finish_listing=scenario.media.work_dir_listings[-1],
        video_text=run.files.to_absolute(f"{OUTPUT_DIR}/{STEM}.mp4").read_text(),
        srt_text=run.files.to_absolute(f"{OUTPUT_DIR}/{STEM}.srt").read_text(),
        is_old_video_kept=old_video.exists(),
        leftover_work=sorted(run.work_root.glob("*")),
    )


@pytest.fixture
def assembled_with_music_and_burn(tmp_path):
    scenario = Scenario(
        project=build_project(allow_music=True, orientation=Orientation.PORTRAIT),
        episode=build_episode(
            burn_subtitles=True,
            subtitle_style=SubtitleStyle.CINEMATIC_GOLD,
            music_status=MediaStatus.DONE,
            music_path=f"{EPISODE_DIR}/music.mp3",
        ),
        scenes=[build_scene(1, **narrated(1, "The fog rolls in."))],
        media=build_media(
            {
                "s1/clip.mp4": SOUND_CLIP_REPORT,
                "s1/narration.wav": to_report("3.200000", ["audio"]),
                JOINED_KEY: to_report("21.000000", ["video", "audio"]),
            }
        ),
    )
    run = run_assembly(tmp_path, scenario)
    result = run.assembler.assemble("e1")
    commands = summarize_commands(scenario.media)
    return SimpleNamespace(
        result=result,
        commands=commands,
        finish_listing=scenario.media.work_dir_listings[-1],
        music_path=str(run.files.to_absolute(f"{EPISODE_DIR}/music.mp3")),
        joined_path=str(commands.work_dir / JOINED_KEY),
    )


@pytest.fixture
def assembled_without_narration(tmp_path):
    scenario = Scenario(
        project=build_project(allow_narration=False, allow_music=True),
        episode=build_episode(
            burn_subtitles=True,
            music_status=MediaStatus.FAILED,
            subtitles_path=f"{OUTPUT_DIR}/Old Title.srt",
        ),
        scenes=tc33_scenes(),
        media=build_media(TC33_REPORTS),
    )
    run = run_assembly(tmp_path, scenario)
    old_srt = write_file(run.files.to_absolute(f"{OUTPUT_DIR}/Old Title.srt"))
    stale_srt = write_file(run.files.to_absolute(f"{OUTPUT_DIR}/{STEM}.srt"))
    result = run.assembler.assemble("e1")
    return SimpleNamespace(
        result=result,
        commands=summarize_commands(scenario.media),
        finish_listing=scenario.media.work_dir_listings[-1],
        is_old_srt_kept=old_srt.exists(),
        is_stale_srt_kept=stale_srt.exists(),
    )


@pytest.fixture
def missing_clip_failure(tmp_path):
    scenes = tc33_scenes()
    scenes[2].clip_status = MediaStatus.NONE
    scenario = Scenario(
        project=build_project(),
        episode=build_episode(),
        scenes=scenes,
        media=build_media(TC33_REPORTS),
    )
    return failed_message(tmp_path, scenario)


@pytest.fixture
def ffmpeg_failure(tmp_path):
    scenario = Scenario(
        project=build_project(),
        episode=build_episode(),
        scenes=tc33_scenes(),
        media=build_media(
            TC33_REPORTS,
            ffmpeg_error=CommandError(
                "ffmpeg-test exited with 1: Invalid data found when processing input"
            ),
        ),
    )
    return failed_message(tmp_path, scenario)


@pytest.fixture
def hung_ffmpeg_failure(tmp_path):
    scenario = Scenario(
        project=build_project(),
        episode=build_episode(),
        scenes=tc33_scenes(),
        media=build_media(
            TC33_REPORTS,
            ffmpeg_error=CommandError("ffmpeg-test timed out after 0.4s"),
            ffmpeg_seconds=1.0,
        ),
        timeout_sec=1,
    )
    return failed_message(tmp_path, scenario)


@pytest.fixture
def slow_assembly(tmp_path):
    scenario = Scenario(
        project=build_project(),
        episode=build_episode(),
        scenes=tc33_scenes(),
        media=build_media(TC33_REPORTS, probe_seconds=2.0, ffmpeg_seconds=2.0),
        timeout_sec=3,
    )
    result = run_assembly(tmp_path, scenario).assembler.assemble("e1")
    return SimpleNamespace(
        result=result, elapsed_sec=scenario.media.clock.now, timeout_sec=scenario.timeout_sec
    )


@pytest.fixture
def quick_ffmpeg_failure_after_slow_probes(tmp_path):
    scenario = Scenario(
        project=build_project(),
        episode=build_episode(),
        scenes=tc33_scenes(),
        media=build_media(
            TC33_REPORTS,
            probe_seconds=2.0,
            ffmpeg_error=CommandError("ffmpeg-test exited with 1: Broken pipe"),
        ),
        timeout_sec=3,
    )
    return failed_message(tmp_path, scenario)


@pytest.fixture
def empty_part_failure(tmp_path):
    scenario = Scenario(
        project=build_project(),
        episode=build_episode(),
        scenes=tc33_scenes(),
        media=build_media(TC33_REPORTS),
        parts=[build_part(1), build_part(2)],
    )
    return failed_message(tmp_path, scenario)


@pytest.fixture
def unreadable_probe_failure(tmp_path):
    scenario = Scenario(
        project=build_project(),
        episode=build_episode(),
        scenes=tc33_scenes(),
        media=build_media({**TC33_REPORTS, "s1/clip.mp4": "not json"}),
    )
    return failed_message(tmp_path, scenario)


@pytest.fixture
def missing_episode_error(tmp_path):
    scenario = Scenario(project=None, episode=None, scenes=[], media=build_media({}))
    with pytest.raises(EpisodeNotFoundError) as error_info:
        run_assembly(tmp_path, scenario).assembler.assemble("e9")
    return str(error_info.value)


@pytest.fixture
def missing_project_error(tmp_path):
    scenario = Scenario(project=None, episode=build_episode(), scenes=[], media=build_media({}))
    with pytest.raises(FilmProjectNotFoundError) as error_info:
        run_assembly(tmp_path, scenario).assembler.assemble("e1")
    return str(error_info.value)


def test_assemble_returns_the_film_paths_and_probed_duration(assembled):
    assert assembled.result == AssembledFilm(
        video_path=f"{OUTPUT_DIR}/{STEM}.mp4",
        subtitles_path=f"{OUTPUT_DIR}/{STEM}.srt",
        duration_ms=17_708,
    )


def test_assemble_writes_the_film_and_one_cue_per_used_narration(assembled):
    assert (assembled.video_text, assembled.srt_text) == ("media", SRT_TEXT)


def test_assemble_probes_every_clip_and_used_narration_then_the_joined_film(assembled):
    assert assembled.commands.probed_keys == [
        "s1/clip.mp4",
        "s1/narration.wav",
        "s2/clip.mp4",
        "s2/narration.wav",
        "s3/clip.mp4",
        "joined.mp4",
    ]


def test_assemble_encodes_each_scene_then_joins_and_finishes(assembled):
    assert assembled.commands.ffmpeg_outputs == [
        "scene-001.mp4",
        "scene-002.mp4",
        "scene-003.mp4",
        "joined.mp4",
        "film.mp4",
    ]


def test_assemble_cuts_each_scene_to_its_planned_length(assembled):
    assert assembled.commands.scene_lengths == ["3.700", "7.000", "7.000"]


def test_assemble_joins_the_scene_files_listed_in_the_work_folder(assembled):
    assert assembled.commands.concat_args == [
        FFMPEG_BIN,
        "-y",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(assembled.commands.work_dir / "scenes.txt"),
        "-c",
        "copy",
        str(assembled.commands.work_dir / "joined.mp4"),
    ]


def test_assemble_copies_the_streams_without_music_or_burned_subtitles(assembled):
    assert assembled.commands.finish_args == [
        FFMPEG_BIN,
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(assembled.commands.work_dir / "joined.mp4"),
        "-map",
        "0:v",
        "-c:v",
        "copy",
        "-map",
        "0:a",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(assembled.commands.work_dir / "film.mp4"),
    ]


def test_assemble_keeps_the_work_files_together_until_the_finish(assembled):
    assert assembled.finish_listing == [
        "joined.mp4",
        "scene-001.mp4",
        "scene-002.mp4",
        "scene-003.mp4",
        "scenes.txt",
        "subtitles.srt",
    ]


def test_assemble_runs_every_command_in_one_temporary_folder_under_the_work_root(
    assembled, tmp_path
):
    assert (assembled.commands.folders, assembled.commands.work_dir.parent) == (
        {assembled.commands.work_dir},
        tmp_path / "work",
    )


def test_assemble_gives_every_command_the_full_timeout(assembled):
    assert assembled.commands.timeouts_sec == {3600.0}


def test_assemble_removes_the_film_saved_under_a_previous_title(assembled):
    assert assembled.is_old_video_kept is False


def test_assemble_removes_the_temporary_work_folder(assembled):
    assert assembled.leftover_work == []


def test_assemble_loops_music_and_burns_subtitles_in_the_finish(assembled_with_music_and_burn):
    assert assembled_with_music_and_burn.commands.finish_args[4:11] == [
        "-i",
        assembled_with_music_and_burn.joined_path,
        "-stream_loop",
        "-1",
        "-i",
        assembled_with_music_and_burn.music_path,
        "-filter_complex",
    ]


def test_assemble_burns_the_chosen_style_and_fades_music_at_the_film_end(
    assembled_with_music_and_burn,
):
    assert assembled_with_music_and_burn.commands.finish_args[11] == (
        "[0:v]subtitles=filename=subtitles.srt:force_style='FontName=Georgia,FontSize=12,"
        "PrimaryColour=&H005CA6C9,OutlineColour=&H00101010,BackColour=&H99000000,BorderStyle=1,"
        "Outline=2.0,Shadow=1.0,MarginL=60,MarginR=60,MarginV=36'[v];"
        "[1:a]volume=0.2,afade=t=out:st=19.000:d=2.000[music];"
        "[0:a][music]amix=inputs=2:duration=first:normalize=0[a]"
    )


def test_assemble_writes_the_subtitles_before_burning_them(assembled_with_music_and_burn):
    assert "subtitles.srt" in assembled_with_music_and_burn.finish_listing


def test_assemble_with_music_keeps_the_probed_film_length(assembled_with_music_and_burn):
    assert assembled_with_music_and_burn.result.duration_ms == 21_000


def test_assemble_without_narration_skips_narration_probes(assembled_without_narration):
    assert assembled_without_narration.commands.probed_keys == [
        "s1/clip.mp4",
        "s2/clip.mp4",
        "s3/clip.mp4",
        "joined.mp4",
    ]


def test_assemble_without_narration_keeps_every_scene_at_its_kept_length(
    assembled_without_narration,
):
    assert assembled_without_narration.commands.scene_lengths == ["7.000", "7.000", "7.000"]


def test_assemble_without_cues_has_no_subtitles(assembled_without_narration):
    assert assembled_without_narration.result.subtitles_path is None


def test_assemble_without_cues_burns_nothing_and_skips_unfinished_music(
    assembled_without_narration,
):
    assert "-filter_complex" not in assembled_without_narration.commands.finish_args


def test_assemble_without_cues_writes_no_subtitles_file(assembled_without_narration):
    assert "subtitles.srt" not in assembled_without_narration.finish_listing


def test_assemble_without_cues_removes_stale_subtitles(assembled_without_narration):
    assert (
        assembled_without_narration.is_old_srt_kept,
        assembled_without_narration.is_stale_srt_kept,
    ) == (False, False)


def test_assemble_names_the_scene_without_a_clip(missing_clip_failure):
    assert missing_clip_failure.message == "Scene 3 has no clip"


def test_assemble_without_a_clip_runs_nothing(missing_clip_failure):
    assert (missing_clip_failure.command_count, missing_clip_failure.leftover_work) == (0, [])


def test_assemble_reports_the_ffmpeg_error(ffmpeg_failure):
    assert ffmpeg_failure.message == (
        "Assembly failed: ffmpeg-test exited with 1: Invalid data found when processing input"
    )


def test_assemble_failure_leaves_no_work_folder_and_no_film(ffmpeg_failure):
    assert (ffmpeg_failure.leftover_work, ffmpeg_failure.output_files) == ([], [])


def test_assemble_reports_a_command_cut_by_its_timeout_as_timed_out(hung_ffmpeg_failure):
    assert hung_ffmpeg_failure.message == "Assembly timed out after 1s"


def test_assemble_timeout_leaves_no_work_folder(hung_ffmpeg_failure):
    assert hung_ffmpeg_failure.leftover_work == []


def test_assemble_lets_a_film_take_longer_than_one_command_timeout(slow_assembly):
    assert slow_assembly.result.duration_ms == 17708
    assert slow_assembly.elapsed_sec > slow_assembly.timeout_sec


def test_assemble_reports_a_quick_ffmpeg_error_after_slow_probes_as_a_failure(
    quick_ffmpeg_failure_after_slow_probes,
):
    assert quick_ffmpeg_failure_after_slow_probes.message == (
        "Assembly failed: ffmpeg-test exited with 1: Broken pipe"
    )


def test_assemble_names_the_part_without_scenes(empty_part_failure):
    assert (empty_part_failure.message, empty_part_failure.command_count) == (
        "Part 2 has no scenes",
        0,
    )


def test_assemble_reports_an_unreadable_probe(unreadable_probe_failure):
    assert unreadable_probe_failure.message == "Assembly failed: ffprobe returned no duration"


def test_assemble_rejects_an_unknown_episode(missing_episode_error):
    assert missing_episode_error == "Episode e9 not found"


def test_assemble_rejects_an_episode_without_its_project(missing_project_error):
    assert missing_project_error == "Film project p1 not found"
