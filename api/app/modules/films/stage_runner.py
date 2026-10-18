import logging
import math
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.db import utc_now
from app.modules.films.errors import EpisodeActionNotAllowedError, FilmConflictError
from app.modules.films.film_access import EpisodeContext, ensure_project_active
from app.modules.films.film_files import FilmFiles
from app.modules.films.media_queue import FilmMediaQueue, SceneOrderContext
from app.modules.films.models import (
    MISSING_MEDIA_STATUSES,
    OPEN_MEDIA_STATUSES,
    Character,
    Episode,
    EpisodeStatus,
    EpisodeStep,
    FilmProject,
    MediaStatus,
    Scene,
    VoiceTemplate,
)
from app.modules.films.repository import FilmRepository
from app.modules.media_generation.models import GenerationRequest
from app.modules.media_generation.service import GenerationService

STAGE_ORDER = (
    EpisodeStep.WRITING_SCRIPT,
    EpisodeStep.GENERATING_REFERENCES,
    EpisodeStep.GENERATING_SCENE_IMAGES,
    EpisodeStep.GENERATING_CLIPS,
    EpisodeStep.GENERATING_AUDIO,
    EpisodeStep.ASSEMBLING,
)
WORKER_STEPS = frozenset({EpisodeStep.WRITING_SCRIPT, EpisodeStep.ASSEMBLING})
STOP_POINT_KEYS_BY_STEP = {
    EpisodeStep.WRITING_SCRIPT: "afterScript",
    EpisodeStep.GENERATING_REFERENCES: "afterReferences",
    EpisodeStep.GENERATING_SCENE_IMAGES: "afterSceneImages",
}
STAGE_FAILED_MESSAGE = "{items} failed — fix them and resume"
FAILED_ITEM_TEMPLATE = "{count} {item}(s)"
NO_NARRATOR_MESSAGE = "Pick a narrator voice for the project or turn narration off"
REWRITE_BLOCKED_MESSAGE = "Scenes already have images or clips — delete them before rewriting"
GENERATION_RUNNING_MESSAGE = "Episode {number} has generation running"
REWRITABLE_STATUSES = frozenset({EpisodeStatus.DRAFT, EpisodeStatus.PAUSED, EpisodeStatus.FAILED})
MS_PER_SECOND = 1000
NEW_MEDIA_STATUSES = frozenset({MediaStatus.NONE})

logger = logging.getLogger(__name__)


class EpisodeAction(StrEnum):
    START = "start"
    CONTINUE = "continue"
    RESUME = "resume"
    STOP = "stop"
    ASSEMBLE = "assemble"
    REWRITE_SCRIPT = "rewrite the script of"


ALLOWED_STATUS_BY_ACTION = {
    EpisodeAction.START: EpisodeStatus.DRAFT,
    EpisodeAction.CONTINUE: EpisodeStatus.PAUSED,
    EpisodeAction.RESUME: EpisodeStatus.FAILED,
    EpisodeAction.STOP: EpisodeStatus.RUNNING,
    EpisodeAction.ASSEMBLE: EpisodeStatus.DONE,
}


class FailedItem(StrEnum):
    REFERENCE_IMAGE = "reference image"
    SCENE_IMAGE = "scene image"
    CLIP = "clip"
    NARRATION = "narration"
    MUSIC_TRACK = "music track"


class StageState(StrEnum):
    WAITING = "waiting"
    FAILED = "failed"
    DONE = "done"


@dataclass(frozen=True)
class StageCheck:
    state: StageState
    failed_counts: tuple[tuple[FailedItem, int], ...] = ()


@dataclass(frozen=True)
class AssembledFilm:
    video_path: str
    subtitles_path: str | None
    duration_ms: int


class ScriptWriter(Protocol):
    def write_script(self, episode_id: str) -> None: ...


class EpisodeAssembler(Protocol):
    def assemble(self, episode_id: str) -> AssembledFilm: ...


@dataclass(frozen=True)
class StageRunnerTools:
    repository: FilmRepository
    files: FilmFiles
    media_queue: FilmMediaQueue
    generation_service: GenerationService
    notify_step_worker: Callable[[], None]
    cancel_worker_step: Callable[[str], None]


@dataclass(frozen=True)
class _StageInputs:
    project: FilmProject
    episode: Episode
    scenes: Sequence[Scene]


class EpisodeStageRunner:
    def __init__(self, tools: StageRunnerTools):
        self._tools = tools
        self._lock = threading.RLock()

    def start(self, context: EpisodeContext) -> Episode:
        with self._lock:
            episode = self._reload_for(context, EpisodeAction.START)
            self._ensure_narrator(context.project)
            self._run_from(
                episode,
                EpisodeStep.WRITING_SCRIPT,
                {"started_at": utc_now(), "finished_at": None, "paused_stop_point": None},
            )
            return self._reload(episode)

    def continue_episode(self, context: EpisodeContext) -> Episode:
        with self._lock:
            episode = self._reload_for(context, EpisodeAction.CONTINUE)
            self._ensure_narrator(context.project)
            self._run_from(episode, episode.step or EpisodeStep.WRITING_SCRIPT, {})
            return self._reload(episode)

    def resume(self, context: EpisodeContext) -> Episode:
        with self._lock:
            episode = self._reload_for(context, EpisodeAction.RESUME)
            self._ensure_narrator(context.project)
            self._run_from(episode, episode.step or EpisodeStep.WRITING_SCRIPT, {})
            return self._reload(episode)

    def assemble(self, context: EpisodeContext) -> Episode:
        with self._lock:
            episode = self._reload_for(context, EpisodeAction.ASSEMBLE)
            self._ensure_narrator(context.project)
            self._run_from(
                episode,
                EpisodeStep.GENERATING_AUDIO,
                {"finished_at": None, "paused_stop_point": None},
            )
            return self._reload(episode)

    def stop(self, context: EpisodeContext) -> Episode:
        with self._lock:
            episode = self._reload_for(context, EpisodeAction.STOP)
            self._tools.repository.update_episode(episode.id, {"status": EpisodeStatus.PAUSED})
            self._tools.generation_service.cancel_queued(
                self._tools.repository.find_open_requests_for_episode(episode.id)
            )
            self._tools.cancel_worker_step(episode.id)
            return self._reload(episode)

    def rewrite_script(self, context: EpisodeContext) -> Episode:
        with self._lock:
            episode = self._reload(context.episode)
            ensure_project_active(context.project)
            if episode.status not in REWRITABLE_STATUSES:
                raise EpisodeActionNotAllowedError(
                    EpisodeAction.REWRITE_SCRIPT, episode.number, episode.status
                )
            if self._tools.repository.find_open_requests_for_episode(episode.id):
                raise FilmConflictError(GENERATION_RUNNING_MESSAGE.format(number=episode.number))
            scenes = self._tools.repository.find_scenes(episode.id)
            if any(scene.image_path or scene.clip_path for scene in scenes):
                raise FilmConflictError(REWRITE_BLOCKED_MESSAGE)
            self._tools.repository.delete_scenes(episode.id)
            for scene in scenes:
                self._tools.files.delete_dir(
                    self._tools.files.scene_dir(context.project.id, episode.id, scene.id)
                )
            self._run_from(
                episode,
                EpisodeStep.WRITING_SCRIPT,
                {"started_at": episode.started_at or utc_now(), "paused_stop_point": None},
            )
            return self._reload(episode)

    def on_request_final(self, request: GenerationRequest) -> None:
        if request.episode_id is not None:
            self.advance(request.episode_id)
            return
        if request.project_id is None:
            return
        for episode in self._tools.repository.find_running_episodes_of_project(request.project_id):
            self.advance(episode.id)

    def advance(self, episode_id: str) -> bool:
        with self._lock:
            episode = self._tools.repository.find_episode(episode_id)
            if episode is None or episode.status is not EpisodeStatus.RUNNING:
                return False
            if episode.step is None or episode.step in WORKER_STEPS:
                return False
            return self._settle_stage(episode, episode.step, NEW_MEDIA_STATUSES)

    def finish_script(self, episode_id: str) -> None:
        with self._lock:
            episode = self._tools.repository.find_episode(episode_id)
            if not _is_running_at(episode, EpisodeStep.WRITING_SCRIPT):
                return
            self._finish_stage(episode, EpisodeStep.WRITING_SCRIPT)

    def finish_assembly(self, episode_id: str, film: AssembledFilm) -> None:
        with self._lock:
            episode = self._tools.repository.find_episode(episode_id)
            if not _is_running_at(episode, EpisodeStep.ASSEMBLING):
                return
            self._tools.repository.update_episode(
                episode_id,
                {
                    "status": EpisodeStatus.DONE,
                    "video_path": film.video_path,
                    "subtitles_path": film.subtitles_path,
                    "duration_ms": film.duration_ms,
                    "needs_assembly": False,
                    "error_message": None,
                    "finished_at": utc_now(),
                },
            )

    def fail_worker_step(self, episode_id: str, step: EpisodeStep, error_message: str) -> None:
        with self._lock:
            episode = self._tools.repository.find_episode(episode_id)
            if not _is_running_at(episode, step):
                return
            self._fail(episode_id, error_message)

    def _reload_for(self, context: EpisodeContext, action: EpisodeAction) -> Episode:
        ensure_project_active(context.project)
        episode = self._reload(context.episode)
        if episode.status is not ALLOWED_STATUS_BY_ACTION[action]:
            raise EpisodeActionNotAllowedError(action, episode.number, episode.status)
        return episode

    def _ensure_narrator(self, project: FilmProject) -> None:
        if project.allow_narration and project.narrator_voice_id is None:
            raise FilmConflictError(NO_NARRATOR_MESSAGE)

    def _run_from(self, episode: Episode, step: EpisodeStep, extra_values: dict) -> None:
        self._tools.repository.update_episode(
            episode.id,
            {
                **extra_values,
                "status": EpisodeStatus.RUNNING,
                "step": step,
                "error_message": None,
            },
        )
        self._enter_stage(self._reload(episode), step)

    def _enter_stage(self, episode: Episode, step: EpisodeStep) -> None:
        if step in WORKER_STEPS:
            self._tools.notify_step_worker()
            return
        self._settle_stage(episode, step, MISSING_MEDIA_STATUSES)

    def _settle_stage(
        self, episode: Episode, step: EpisodeStep, queued_statuses: frozenset[MediaStatus]
    ) -> bool:
        self._queue_stage(self._load_inputs(episode), step, queued_statuses)
        check = self._check_stage(self._load_inputs(episode), step)
        if check.state is StageState.WAITING:
            return False
        if check.state is StageState.FAILED:
            self._fail(episode.id, _to_failed_message(check.failed_counts))
            return True
        self._finish_stage(episode, step)
        return True

    def _finish_stage(self, episode: Episode, step: EpisodeStep) -> None:
        stop_point_key = STOP_POINT_KEYS_BY_STEP.get(step)
        is_stop_point = bool(stop_point_key and (episode.stop_points or {}).get(stop_point_key))
        if is_stop_point and episode.paused_stop_point is not step:
            self._tools.repository.update_episode(
                episode.id, {"status": EpisodeStatus.PAUSED, "paused_stop_point": step}
            )
            return
        next_step = STAGE_ORDER[STAGE_ORDER.index(step) + 1]
        self._tools.repository.update_episode(episode.id, {"step": next_step})
        self._enter_stage(self._reload(episode), next_step)

    def _fail(self, episode_id: str, error_message: str) -> None:
        self._tools.repository.update_episode(
            episode_id, {"status": EpisodeStatus.FAILED, "error_message": error_message}
        )

    def _load_inputs(self, episode: Episode) -> _StageInputs:
        project = self._tools.repository.find_project(episode.project_id)
        if project is None:
            raise LookupError(episode.project_id)
        return _StageInputs(
            project=project,
            episode=self._reload(episode),
            scenes=self._tools.repository.find_scenes(episode.id),
        )

    def _queue_stage(
        self, inputs: _StageInputs, step: EpisodeStep, statuses: frozenset[MediaStatus]
    ) -> None:
        if step is EpisodeStep.GENERATING_REFERENCES:
            self._queue_references(inputs, statuses)
        elif step is EpisodeStep.GENERATING_SCENE_IMAGES:
            self._queue_scene_media(
                inputs, statuses, _image_status, FilmMediaQueue.queue_scene_image
            )
        elif step is EpisodeStep.GENERATING_CLIPS:
            self._queue_scene_media(inputs, statuses, _clip_status, FilmMediaQueue.queue_scene_clip)
        else:
            self._queue_audio(inputs, statuses)

    def _queue_references(self, inputs: _StageInputs, statuses: frozenset[MediaStatus]) -> None:
        for character in self._scene_characters(inputs.scenes):
            if character.reference_status in statuses:
                self._tools.media_queue.queue_character_image(
                    inputs.project, character, inputs.episode.id
                )

    def _queue_scene_media(
        self,
        inputs: _StageInputs,
        statuses: frozenset[MediaStatus],
        read_status: Callable[[Scene], MediaStatus],
        queue: Callable[[FilmMediaQueue, SceneOrderContext], GenerationRequest],
    ) -> None:
        for scene in inputs.scenes:
            if read_status(scene) in statuses:
                queue(
                    self._tools.media_queue,
                    SceneOrderContext(inputs.project, inputs.episode.id, scene),
                )

    def _queue_audio(self, inputs: _StageInputs, statuses: frozenset[MediaStatus]) -> None:
        voice = self._narrator_voice(inputs.project)
        if voice is not None:
            for scene in _narrated_scenes(inputs):
                if scene.narration_status in statuses:
                    self._tools.media_queue.queue_narration(
                        SceneOrderContext(inputs.project, inputs.episode.id, scene), voice
                    )
        if _wants_music(inputs) and inputs.episode.music_status in statuses:
            self._tools.media_queue.queue_music(
                inputs.project, inputs.episode, _to_music_length_s(inputs.scenes)
            )

    def _check_stage(self, inputs: _StageInputs, step: EpisodeStep) -> StageCheck:
        if step is EpisodeStep.GENERATING_REFERENCES:
            characters = self._scene_characters(inputs.scenes)
            return _to_stage_check(
                [(FailedItem.REFERENCE_IMAGE, [c.reference_status for c in characters])]
            )
        if step is EpisodeStep.GENERATING_SCENE_IMAGES:
            return _to_stage_check(
                [(FailedItem.SCENE_IMAGE, [_image_status(s) for s in inputs.scenes])]
            )
        if step is EpisodeStep.GENERATING_CLIPS:
            return _to_stage_check([(FailedItem.CLIP, [_clip_status(s) for s in inputs.scenes])])
        narration_statuses = (
            [scene.narration_status for scene in _narrated_scenes(inputs)]
            if self._narrator_voice(inputs.project) is not None
            else []
        )
        music_statuses = [inputs.episode.music_status] if _wants_music(inputs) else []
        return _to_stage_check(
            [
                (FailedItem.NARRATION, narration_statuses),
                (FailedItem.MUSIC_TRACK, music_statuses),
            ]
        )

    def _scene_characters(self, scenes: Sequence[Scene]) -> list[Character]:
        character_ids = list(
            dict.fromkeys(character_id for scene in scenes for character_id in scene.character_ids)
        )
        characters_by_id = self._tools.repository.find_characters_by_ids(character_ids)
        return [characters_by_id[cid] for cid in character_ids if cid in characters_by_id]

    def _narrator_voice(self, project: FilmProject) -> VoiceTemplate | None:
        if not project.allow_narration or project.narrator_voice_id is None:
            return None
        return self._tools.repository.find_voice(project.narrator_voice_id)

    def _reload(self, episode: Episode) -> Episode:
        return self._tools.repository.find_episode(episode.id) or episode


def _is_running_at(episode: Episode | None, step: EpisodeStep) -> bool:
    return episode is not None and episode.status is EpisodeStatus.RUNNING and episode.step is step


def _image_status(scene: Scene) -> MediaStatus:
    return scene.image_status


def _clip_status(scene: Scene) -> MediaStatus:
    return scene.clip_status


def _narrated_scenes(inputs: _StageInputs) -> list[Scene]:
    return [scene for scene in inputs.scenes if scene.narrator_text and scene.narrator_text.strip()]


def _wants_music(inputs: _StageInputs) -> bool:
    music_prompt = inputs.episode.music_prompt
    return inputs.project.allow_music and bool(music_prompt and music_prompt.strip())


def _to_music_length_s(scenes: Sequence[Scene]) -> int:
    kept_ms = sum(_kept_clip_ms(scene) for scene in scenes)
    return math.ceil(kept_ms / MS_PER_SECOND)


def _kept_clip_ms(scene: Scene) -> int:
    clip_end_ms = scene.trim_end_ms or scene.clip_duration_ms or 0
    return max(clip_end_ms - scene.trim_start_ms, 0)


def _to_stage_check(
    statuses_by_item: Sequence[tuple[FailedItem, Sequence[MediaStatus]]],
) -> StageCheck:
    all_statuses = [status for _, statuses in statuses_by_item for status in statuses]
    if any(status in OPEN_MEDIA_STATUSES for status in all_statuses):
        return StageCheck(StageState.WAITING)
    failed_counts = tuple(
        (item, count)
        for item, statuses in statuses_by_item
        if (count := sum(1 for status in statuses if status is MediaStatus.FAILED))
    )
    if failed_counts:
        return StageCheck(StageState.FAILED, failed_counts)
    if any(status is MediaStatus.NONE for status in all_statuses):
        return StageCheck(StageState.WAITING)
    return StageCheck(StageState.DONE)


def _to_failed_message(failed_counts: Sequence[tuple[FailedItem, int]]) -> str:
    items = " and ".join(
        FAILED_ITEM_TEMPLATE.format(count=count, item=item.value) for item, count in failed_counts
    )
    return STAGE_FAILED_MESSAGE.format(items=items)
