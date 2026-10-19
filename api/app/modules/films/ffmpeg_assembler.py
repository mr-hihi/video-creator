import shutil
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from app.common.process import Command, CommandError, CommandRunner
from app.modules.films.assembly_commands import (
    BurnedSubtitles,
    FilmFinish,
    MediaFacts,
    MusicMix,
    SceneEncoding,
    build_concat_args,
    build_concat_list_text,
    build_finish_args,
    build_probe_args,
    build_scene_encode_args,
    ffprobe_json_to_media_facts,
)
from app.modules.films.assembly_plan import (
    ASSEMBLY_FAILED_MESSAGE,
    NarrationTake,
    SceneCut,
    SceneSource,
    SubtitleCue,
    build_assembly_plan,
    ensure_every_clip_done,
    ensure_every_part_has_scenes,
    is_music_used,
    is_narration_used,
    to_srt_text,
)
from app.modules.films.errors import (
    EpisodeNotFoundError,
    EpisodeStepFailedError,
    FilmProjectNotFoundError,
)
from app.modules.films.film_access import EpisodeContext
from app.modules.films.film_files import FilmFiles
from app.modules.films.film_outputs import FilmOutput, build_output_file_name
from app.modules.films.models import EpisodePart, Scene
from app.modules.films.repository import FilmRepository
from app.modules.films.stage_runner import AssembledFilm

ASSEMBLY_TIMED_OUT_MESSAGE = "Assembly timed out after {timeout_sec}s"
WORK_DIR_PREFIX = "film-assembly-"
SCENE_FILE_NAME = "scene-{number:03d}.mp4"
CONCAT_LIST_FILE_NAME = "scenes.txt"
JOINED_FILE_NAME = "joined.mp4"
FILM_FILE_NAME = "film.mp4"
SUBTITLES_FILE_NAME = "subtitles.srt"
TEXT_ENCODING = "utf-8"
FFMPEG_QUIET_ARGS = ("-y", "-loglevel", "error")


@dataclass(frozen=True)
class AssemblerConfig:
    ffmpeg_bin: str
    ffprobe_bin: str
    timeout_sec: int
    music_volume: float
    work_root: Path


@dataclass(frozen=True)
class AssemblerTools:
    repository: FilmRepository
    files: FilmFiles
    runner: CommandRunner
    clock: Callable[[], float] = field(default=time.monotonic)


@dataclass(frozen=True)
class _EpisodeInputs:
    context: EpisodeContext
    parts: Sequence[EpisodePart]
    scenes: Sequence[Scene]


@dataclass(frozen=True)
class _JoinedFilm:
    path: Path
    duration_ms: int


@dataclass(frozen=True)
class _FinishedFilm:
    path: Path
    duration_ms: int
    work_subtitles_path: Path | None


class _TimedCommands:
    def __init__(self, config: AssemblerConfig, tools: AssemblerTools):
        self._config = config
        self._runner = tools.runner
        self._clock = tools.clock

    def run_ffmpeg(self, arguments: Sequence[str], work_dir: Path) -> None:
        self._run([self._config.ffmpeg_bin, *FFMPEG_QUIET_ARGS, *arguments], work_dir)

    def probe(self, media_path: Path, work_dir: Path) -> MediaFacts:
        stdout = self._run([self._config.ffprobe_bin, *build_probe_args(media_path)], work_dir)
        try:
            return ffprobe_json_to_media_facts(stdout)
        except CommandError as error:
            raise _to_failed_error(error) from error

    def _run(self, command_args: list[str], work_dir: Path) -> str:
        started_sec = self._clock()
        try:
            return self._runner.run(
                Command(args=command_args, timeout_sec=self._config.timeout_sec, cwd=work_dir)
            )
        except CommandError as error:
            if self._clock() - started_sec >= self._config.timeout_sec:
                raise EpisodeStepFailedError(
                    ASSEMBLY_TIMED_OUT_MESSAGE.format(timeout_sec=self._config.timeout_sec)
                ) from error
            raise _to_failed_error(error) from error


def _to_failed_error(error: CommandError) -> EpisodeStepFailedError:
    return EpisodeStepFailedError(ASSEMBLY_FAILED_MESSAGE.format(error=error))


@dataclass(frozen=True)
class _AssemblySetup:
    config: AssemblerConfig
    files: FilmFiles
    commands: _TimedCommands
    work_dir: Path


class _EpisodeAssembly:
    def __init__(self, setup: _AssemblySetup, inputs: _EpisodeInputs):
        self._setup = setup
        self._context = inputs.context
        self._scenes = inputs.scenes

    def run(self) -> AssembledFilm:
        plan = build_assembly_plan([self._to_scene_source(scene) for scene in self._scenes])
        work_subtitles_path = self._write_work_subtitles(plan.cues)
        joined = self._join(plan.cuts)
        film_path = self._finish(joined, work_subtitles_path)
        return self._save_outputs(_FinishedFilm(film_path, joined.duration_ms, work_subtitles_path))

    def _to_scene_source(self, scene: Scene) -> SceneSource:
        clip_path = self._setup.files.to_absolute(scene.clip_path or "")
        clip = self._probe(clip_path)
        return SceneSource(
            clip_path=clip_path,
            clip_duration_ms=clip.duration_ms,
            has_clip_sound=clip.has_sound,
            trim_start_ms=scene.trim_start_ms,
            trim_end_ms=scene.trim_end_ms,
            narration=self._to_narration_take(scene),
        )

    def _to_narration_take(self, scene: Scene) -> NarrationTake | None:
        if not is_narration_used(self._context.project, scene):
            return None
        narration_path = self._setup.files.to_absolute(scene.narration_path or "")
        return NarrationTake(
            path=narration_path,
            duration_ms=self._probe(narration_path).duration_ms,
            text=scene.narrator_text or "",
        )

    def _write_work_subtitles(self, cues: Sequence[SubtitleCue]) -> Path | None:
        if not cues:
            return None
        subtitles_path = self._setup.work_dir / SUBTITLES_FILE_NAME
        subtitles_path.write_text(to_srt_text(cues), encoding=TEXT_ENCODING)
        return subtitles_path

    def _join(self, cuts: Sequence[SceneCut]) -> _JoinedFilm:
        scene_file_names = [
            self._encode_scene(number, cut) for number, cut in enumerate(cuts, start=1)
        ]
        list_path = self._setup.work_dir / CONCAT_LIST_FILE_NAME
        list_path.write_text(build_concat_list_text(scene_file_names), encoding=TEXT_ENCODING)
        joined_path = self._setup.work_dir / JOINED_FILE_NAME
        self._run_ffmpeg(build_concat_args(list_path, joined_path))
        return _JoinedFilm(joined_path, self._probe(joined_path).duration_ms)

    def _encode_scene(self, number: int, cut: SceneCut) -> str:
        file_name = SCENE_FILE_NAME.format(number=number)
        encoding = SceneEncoding(
            cut=cut,
            orientation=self._context.project.orientation,
            output_path=self._setup.work_dir / file_name,
        )
        self._run_ffmpeg(build_scene_encode_args(encoding))
        return file_name

    def _finish(self, joined: _JoinedFilm, work_subtitles_path: Path | None) -> Path:
        finish = FilmFinish(
            joined_path=joined.path,
            output_path=self._setup.work_dir / FILM_FILE_NAME,
            music=self._to_music_mix(joined.duration_ms),
            subtitles=self._to_burned_subtitles(work_subtitles_path),
        )
        self._run_ffmpeg(build_finish_args(finish))
        return finish.output_path

    def _to_music_mix(self, film_ms: int) -> MusicMix | None:
        episode = self._context.episode
        if not is_music_used(self._context.project, episode):
            return None
        return MusicMix(
            music_path=self._setup.files.to_absolute(episode.music_path or ""),
            volume=self._setup.config.music_volume,
            film_ms=film_ms,
        )

    def _to_burned_subtitles(self, work_subtitles_path: Path | None) -> BurnedSubtitles | None:
        if work_subtitles_path is None or not self._context.episode.burn_subtitles:
            return None
        return BurnedSubtitles(
            file_name=work_subtitles_path.name,
            style=self._context.episode.subtitle_style,
            orientation=self._context.project.orientation,
        )

    def _save_outputs(self, film: _FinishedFilm) -> AssembledFilm:
        video_path = self._output_path(FilmOutput.VIDEO)
        video_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(film.path, video_path)
        video_relative_path = self._setup.files.to_relative(video_path)
        subtitles_relative_path = self._save_subtitles(film.work_subtitles_path)
        self._remove_replaced(self._context.episode.video_path, video_relative_path)
        self._remove_replaced(self._context.episode.subtitles_path, subtitles_relative_path)
        return AssembledFilm(
            video_path=video_relative_path,
            subtitles_path=subtitles_relative_path,
            duration_ms=film.duration_ms,
        )

    def _save_subtitles(self, work_subtitles_path: Path | None) -> str | None:
        subtitles_path = self._output_path(FilmOutput.SUBTITLES)
        if work_subtitles_path is None:
            subtitles_path.unlink(missing_ok=True)
            return None
        shutil.copyfile(work_subtitles_path, subtitles_path)
        return self._setup.files.to_relative(subtitles_path)

    def _remove_replaced(self, previous_path: str | None, current_path: str | None) -> None:
        if previous_path != current_path:
            self._setup.files.delete(previous_path)

    def _output_path(self, output: FilmOutput) -> Path:
        output_dir = self._setup.files.output_dir(
            self._context.project.id, self._context.episode.id
        )
        return output_dir / build_output_file_name(self._context, output)

    def _run_ffmpeg(self, arguments: Sequence[str]) -> None:
        self._setup.commands.run_ffmpeg(arguments, self._setup.work_dir)

    def _probe(self, media_path: Path) -> MediaFacts:
        return self._setup.commands.probe(media_path, self._setup.work_dir)


class FfmpegEpisodeAssembler:
    def __init__(self, config: AssemblerConfig, tools: AssemblerTools):
        self._config = config
        self._tools = tools

    def assemble(self, episode_id: str) -> AssembledFilm:
        inputs = self._load_inputs(episode_id)
        ensure_every_part_has_scenes(inputs.parts, inputs.scenes)
        ensure_every_clip_done(inputs.scenes)
        self._config.work_root.mkdir(parents=True, exist_ok=True)
        work_dir = Path(tempfile.mkdtemp(prefix=WORK_DIR_PREFIX, dir=self._config.work_root))
        try:
            setup = _AssemblySetup(
                config=self._config,
                files=self._tools.files,
                commands=_TimedCommands(self._config, self._tools),
                work_dir=work_dir,
            )
            return _EpisodeAssembly(setup, inputs).run()
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def _load_inputs(self, episode_id: str) -> _EpisodeInputs:
        episode = self._tools.repository.find_episode(episode_id)
        if episode is None:
            raise EpisodeNotFoundError(episode_id)
        project = self._tools.repository.find_project(episode.project_id)
        if project is None:
            raise FilmProjectNotFoundError(episode.project_id)
        return _EpisodeInputs(
            context=EpisodeContext(project=project, episode=episode),
            parts=self._tools.repository.find_parts(episode_id),
            scenes=self._tools.repository.find_scenes(episode_id),
        )
