from collections.abc import Sequence
from dataclasses import dataclass
from itertools import accumulate
from pathlib import Path

from app.modules.films.errors import EpisodeStepFailedError
from app.modules.films.models import Episode, EpisodePart, FilmProject, MediaStatus, Scene
from app.modules.films.part_rules import to_part_number

NARRATION_TAIL_MS = 500
NO_CLIP_MESSAGE = "Scene {number} has no clip"
NO_PART_SCENES_MESSAGE = "Part {number} has no scenes"
ASSEMBLY_FAILED_MESSAGE = "Assembly failed: {error}"
NO_SCENES_ERROR = "the episode has no scenes"
SRT_TIME_FORMAT = "{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
MS_PER_SECOND = 1000
SECONDS_PER_MINUTE = 60
MINUTES_PER_HOUR = 60


@dataclass(frozen=True)
class NarrationTake:
    path: Path
    duration_ms: int
    text: str


@dataclass(frozen=True)
class SceneSource:
    clip_path: Path
    clip_duration_ms: int
    has_clip_sound: bool
    trim_start_ms: int
    trim_end_ms: int | None
    narration: NarrationTake | None


@dataclass(frozen=True)
class SceneCut:
    clip_path: Path
    has_clip_sound: bool
    clip_start_ms: int
    length_ms: int
    narration: NarrationTake | None


@dataclass(frozen=True)
class SubtitleCue:
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class SceneSpan:
    start_ms: int
    length_ms: int


@dataclass(frozen=True)
class AssemblyPlan:
    cuts: tuple[SceneCut, ...]
    cues: tuple[SubtitleCue, ...]


def ensure_every_part_has_scenes(parts: Sequence[EpisodePart], scenes: Sequence[Scene]) -> None:
    part_ids_with_scenes = {scene.part_id for scene in scenes}
    for part in parts:
        if part.id not in part_ids_with_scenes:
            raise EpisodeStepFailedError(
                NO_PART_SCENES_MESSAGE.format(number=to_part_number(part.position))
            )


def ensure_every_clip_done(scenes: Sequence[Scene]) -> None:
    if not scenes:
        raise EpisodeStepFailedError(ASSEMBLY_FAILED_MESSAGE.format(error=NO_SCENES_ERROR))
    for number, scene in enumerate(scenes, start=1):
        if scene.clip_status is not MediaStatus.DONE or not scene.clip_path:
            raise EpisodeStepFailedError(NO_CLIP_MESSAGE.format(number=number))


def is_narration_used(project: FilmProject, scene: Scene) -> bool:
    return (
        project.allow_narration
        and scene.narration_status is MediaStatus.DONE
        and scene.narration_path is not None
    )


def is_music_used(project: FilmProject, episode: Episode) -> bool:
    return (
        project.allow_music
        and episode.music_status is MediaStatus.DONE
        and episode.music_path is not None
    )


def measure_kept_ms(source: SceneSource) -> int:
    kept_end_ms = (
        source.clip_duration_ms
        if source.trim_end_ms is None
        else min(source.trim_end_ms, source.clip_duration_ms)
    )
    return max(kept_end_ms - source.trim_start_ms, 0)


def measure_scene_ms(source: SceneSource) -> int:
    kept_ms = measure_kept_ms(source)
    if source.narration is None:
        return kept_ms
    return min(source.narration.duration_ms + NARRATION_TAIL_MS, kept_ms)


def to_scene_cut(source: SceneSource) -> SceneCut:
    return SceneCut(
        clip_path=source.clip_path,
        has_clip_sound=source.has_clip_sound,
        clip_start_ms=source.trim_start_ms,
        length_ms=measure_scene_ms(source),
        narration=source.narration,
    )


def build_assembly_plan(sources: Sequence[SceneSource]) -> AssemblyPlan:
    cuts = tuple(to_scene_cut(source) for source in sources)
    start_times_ms = accumulate((cut.length_ms for cut in cuts), initial=0)
    cues = tuple(
        to_subtitle_cue(cut.narration, SceneSpan(start_ms, cut.length_ms))
        for cut, start_ms in zip(cuts, start_times_ms, strict=False)
        if cut.narration is not None
    )
    return AssemblyPlan(cuts=cuts, cues=cues)


def to_subtitle_cue(narration: NarrationTake, span: SceneSpan) -> SubtitleCue:
    return SubtitleCue(
        start_ms=span.start_ms,
        end_ms=span.start_ms + min(narration.duration_ms, span.length_ms),
        text=narration.text,
    )


def to_srt_text(cues: Sequence[SubtitleCue]) -> str:
    return "\n".join(
        f"{number}\n{format_srt_time(cue.start_ms)} --> {format_srt_time(cue.end_ms)}\n"
        f"{to_cue_lines(cue.text)}\n"
        for number, cue in enumerate(cues, start=1)
    )


def to_cue_lines(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def format_srt_time(at_ms: int) -> str:
    total_seconds, milliseconds = divmod(at_ms, MS_PER_SECOND)
    total_minutes, seconds = divmod(total_seconds, SECONDS_PER_MINUTE)
    hours, minutes = divmod(total_minutes, MINUTES_PER_HOUR)
    return SRT_TIME_FORMAT.format(
        hours=hours, minutes=minutes, seconds=seconds, milliseconds=milliseconds
    )
