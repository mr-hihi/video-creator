from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.modules.ai_models.ai_calls import AiStepGroup
from app.modules.ai_models.step_models import AiStepModels
from app.modules.films.analysis_source import AnalysisSource
from app.modules.films.clone_source import CloneImportTarget, CloneSource
from app.modules.films.episode_rules import (
    build_default_title,
    to_valid_idea,
    to_valid_target_duration,
    to_valid_title,
)
from app.modules.films.errors import (
    EpisodeRunningError,
    FilmConflictError,
    InvalidFilmRequestError,
)
from app.modules.films.film_access import EpisodeContext, FilmAccess
from app.modules.films.film_files import FilmFiles
from app.modules.films.film_imports import FilmImports
from app.modules.films.media_queue import CANDIDATE_PARAM
from app.modules.films.models import (
    Episode,
    EpisodeSource,
    EpisodeStatus,
    FilmProject,
    MediaStatus,
    SubtitleStyle,
)
from app.modules.films.part_service import to_part_counts
from app.modules.films.repository import EpisodeCreation, FilmRepository
from app.modules.films.story_rules import to_valid_summary
from app.modules.films.views import (
    CUT_HEAD_S,
    EpisodeDetail,
    EpisodeSummary,
    PartSummary,
    ThumbnailCandidate,
)
from app.modules.media_generation.models import GenerationKind, GenerationRequest, GenerationStatus
from app.modules.prompt_presets.errors import PromptPresetNotFoundError
from app.modules.prompt_presets.service import PresetSnapshot, PromptPresetService

DRAFT_ONLY_MESSAGE = "Idea and target length can change only before the episode starts"
EPISODE_GENERATION_RUNNING_MESSAGE = "Episode {number} has generation running"
THUMBNAIL_CANDIDATES = (1, 2, 3, 4)
RUNNING_EDITABLE_FIELDS = frozenset({"stop_points"})
DRAFT_ONLY_FIELDS = frozenset({"idea", "target_duration_s"})
SETTING_FIELDS = ("stop_points", "burn_subtitles", "subtitle_style")
ASSEMBLY_FIELDS = ("burn_subtitles", "subtitle_style", "music_prompt")
MUSIC_RESET = {"music_status": MediaStatus.NONE, "music_path": None, "music_error": None}


@dataclass(frozen=True)
class EpisodeDraft:
    source: EpisodeSource
    idea: str | None
    source_job_id: str | None
    source_clone_id: str | None
    target_duration_s: int
    stop_points: Mapping[str, bool]
    burn_subtitles: bool
    subtitle_style: SubtitleStyle
    preset_id: str | None


@dataclass(frozen=True)
class EpisodeServiceTools:
    repository: FilmRepository
    access: FilmAccess
    files: FilmFiles
    imports: FilmImports
    preset_service: PromptPresetService
    step_models: AiStepModels
    analysis_source: AnalysisSource
    clone_source: CloneSource


class EpisodeService:
    def __init__(self, tools: EpisodeServiceTools):
        self._tools = tools

    def create_episode(self, project_id: str, draft: EpisodeDraft) -> EpisodeSummary:
        project = self._tools.access.get_active_project(project_id)
        episode = self._build_episode(project, draft)
        if draft.source is EpisodeSource.FILM_CLONE:
            added = self._add_cloned_episode(project, episode)
        elif draft.source is EpisodeSource.FILM_ANALYSIS:
            added = self._add_with_files(
                EpisodeCreation(episode),
                lambda: self._tools.analysis_source.copy_into(episode),
            )
        else:
            added = self._tools.repository.add_episode(EpisodeCreation(episode))
        return EpisodeSummary(self._ensure_default_title(added))

    def get_episode_detail(self, episode_id: str) -> EpisodeDetail:
        context = self._tools.access.get_episode(episode_id)
        episode = context.episode
        open_requests = self._tools.repository.find_open_requests_for_episode(episode.id)
        return EpisodeDetail(
            summary=EpisodeSummary(episode),
            project=context.project,
            parts=self._summarize_parts(episode.id, open_requests),
            open_requests=[request for request in open_requests if request.scene_id is None],
            thumbnail_candidates=self._find_thumbnail_candidates(episode.id),
            is_source_deleted=self._is_source_deleted(episode),
        )

    def update_episode(self, episode_id: str, changes: Mapping[str, Any]) -> EpisodeSummary:
        context = self._tools.access.get_writable_episode(episode_id)
        ensure_fields_editable(context.episode, changes)
        values = self._to_episode_values(context, changes)
        if values:
            self._tools.repository.update_episode(episode_id, values)
        if "music_status" in values:
            self._tools.files.delete(context.episode.music_path)
        return EpisodeSummary(self._reload(context.episode))

    def delete_episode(self, episode_id: str) -> None:
        context = self._tools.access.get_writable_episode(episode_id)
        episode = context.episode
        if self._tools.repository.find_open_requests_for_episode(episode.id):
            raise FilmConflictError(
                EPISODE_GENERATION_RUNNING_MESSAGE.format(number=episode.number)
            )
        self._tools.repository.delete_episode(episode.id)
        self._tools.files.delete_dir(self._tools.files.episode_dir(context.project.id, episode.id))

    def _build_episode(self, project: FilmProject, draft: EpisodeDraft) -> Episode:
        idea = to_valid_idea(draft.idea, draft.source)
        source_job_id = self._to_source_job_id(draft)
        if draft.source is not EpisodeSource.FILM_CLONE:
            to_valid_target_duration(draft.target_duration_s)
        snapshot = self._get_preset_snapshot(draft.preset_id)
        self._tools.step_models.ensure_set_up((AiStepGroup.FILM_SCRIPT,))
        number = project.last_episode_number + 1
        is_clone = draft.source is EpisodeSource.FILM_CLONE
        return Episode(
            id=str(uuid4()),
            project_id=project.id,
            number=number,
            title=build_default_title(number),
            source=draft.source,
            idea=idea,
            source_job_id=source_job_id,
            source_clone_id=draft.source_clone_id if is_clone else None,
            target_duration_s=draft.target_duration_s,
            stop_points=dict(draft.stop_points),
            burn_subtitles=draft.burn_subtitles,
            subtitle_style=draft.subtitle_style,
            music_status=MediaStatus.NONE,
            preset={"id": snapshot.preset_id, "name": snapshot.name, "version": snapshot.version},
            film_outline_prompt=snapshot.prompts.film_outline,
            film_script_prompt=snapshot.prompts.film_script,
            story_bible_prompt=snapshot.prompts.story_bible,
            status=EpisodeStatus.DRAFT,
            step=None,
            needs_assembly=False,
        )

    def _to_source_job_id(self, draft: EpisodeDraft) -> str | None:
        if draft.source is not EpisodeSource.FILM_ANALYSIS:
            return None
        return self._tools.analysis_source.get_done_job(draft.source_job_id).id

    def _get_preset_snapshot(self, preset_id: str | None) -> PresetSnapshot:
        try:
            return self._tools.preset_service.get_job_snapshot(preset_id)
        except PromptPresetNotFoundError as error:
            raise InvalidFilmRequestError(str(error)) from error

    def _add_cloned_episode(self, project: FilmProject, episode: Episode) -> Episode:
        clone = self._tools.clone_source.get_done_clone(episode.source_clone_id, project)
        clone_import = self._tools.clone_source.plan_import(
            clone, CloneImportTarget(project=project, episode_id=episode.id)
        )
        episode.target_duration_s = len(clone_import.scenes) * (
            project.clip_duration_s - CUT_HEAD_S
        )
        creation = EpisodeCreation(
            episode=episode,
            new_characters=clone_import.new_characters,
            linked_character_ids=clone_import.linked_character_ids,
            parts=clone_import.parts,
            scenes=clone_import.scenes,
        )
        return self._add_with_files(
            creation, lambda: self._tools.imports.copy_files(clone_import.file_copies)
        )

    def _add_with_files(self, creation: EpisodeCreation, copy_files: Callable[[], None]) -> Episode:
        episode = creation.episode
        try:
            copy_files()
            return self._tools.repository.add_episode(creation)
        except Exception:
            self._tools.files.delete_dir(
                self._tools.files.episode_dir(episode.project_id, episode.id)
            )
            for character in creation.new_characters:
                self._tools.files.delete_dir(self._tools.files.character_dir(character.id))
            raise

    def _ensure_default_title(self, episode: Episode) -> Episode:
        default_title = build_default_title(episode.number)
        if episode.title == default_title:
            return episode
        self._tools.repository.update_episode(episode.id, {"title": default_title})
        return self._reload(episode)

    def _to_episode_values(
        self, context: EpisodeContext, changes: Mapping[str, Any]
    ) -> dict[str, Any]:
        episode = context.episode
        values: dict[str, Any] = {
            name: changes[name]
            for name in SETTING_FIELDS
            if name in changes and changes[name] is not None
        }
        if "title" in changes:
            values["title"] = to_valid_title(changes["title"])
        if "idea" in changes:
            values["idea"] = to_valid_idea(changes["idea"], episode.source)
        if "target_duration_s" in changes:
            values["target_duration_s"] = to_valid_target_duration(changes["target_duration_s"])
        if "thumbnail_prompt" in changes:
            values["thumbnail_prompt"] = to_optional_prompt(changes["thumbnail_prompt"])
        if "summary" in changes:
            values["summary"] = to_valid_summary(changes["summary"])
        values.update(to_music_values(episode, changes))
        if episode.status is EpisodeStatus.DONE and is_assembly_change(episode, values):
            values["needs_assembly"] = True
        return values

    def _summarize_parts(
        self, episode_id: str, open_requests: Sequence[GenerationRequest]
    ) -> list[PartSummary]:
        scenes = self._tools.repository.find_scenes(episode_id)
        return [
            PartSummary(
                part=part,
                counts=to_part_counts(
                    [scene for scene in scenes if scene.part_id == part.id], open_requests
                ),
            )
            for part in self._tools.repository.find_parts(episode_id)
        ]

    def _find_thumbnail_candidates(self, episode_id: str) -> list[ThumbnailCandidate]:
        newest_by_candidate: dict[int, GenerationRequest] = {}
        for request in self._tools.repository.find_latest_requests(
            episode_id, GenerationKind.THUMBNAIL
        ):
            newest_by_candidate.setdefault(int(request.params.get(CANDIDATE_PARAM, 0)), request)
        return [
            self._to_thumbnail_candidate(candidate, newest_by_candidate[candidate])
            for candidate in THUMBNAIL_CANDIDATES
            if candidate in newest_by_candidate
        ]

    def _to_thumbnail_candidate(
        self, candidate: int, request: GenerationRequest
    ) -> ThumbnailCandidate:
        return ThumbnailCandidate(
            candidate=candidate,
            status=request.status,
            path=self._to_ready_output_path(request),
            error_message=request.error_message,
        )

    def _to_ready_output_path(self, request: GenerationRequest) -> str | None:
        if request.status is not GenerationStatus.DONE or request.output_path is None:
            return None
        return self._tools.files.to_relative(Path(request.output_path))

    def _is_source_deleted(self, episode: Episode) -> bool:
        if episode.source is EpisodeSource.FILM_ANALYSIS:
            return not self._tools.analysis_source.has_job(episode.source_job_id)
        if episode.source is EpisodeSource.FILM_CLONE:
            return not self._tools.clone_source.has_clone(episode.source_clone_id)
        return False

    def _reload(self, episode: Episode) -> Episode:
        return self._tools.repository.find_episode(episode.id) or episode


def ensure_fields_editable(episode: Episode, changes: Mapping[str, Any]) -> None:
    changed_fields = set(changes)
    if episode.status is EpisodeStatus.RUNNING and changed_fields - RUNNING_EDITABLE_FIELDS:
        raise EpisodeRunningError(episode.number)
    if episode.status is not EpisodeStatus.DRAFT and changed_fields & DRAFT_ONLY_FIELDS:
        raise FilmConflictError(DRAFT_ONLY_MESSAGE)


def to_optional_prompt(prompt: str | None) -> str | None:
    return (prompt or "").strip() or None


def to_music_values(episode: Episode, changes: Mapping[str, Any]) -> dict[str, Any]:
    if "music_prompt" not in changes:
        return {}
    music_prompt = to_optional_prompt(changes["music_prompt"])
    if music_prompt == episode.music_prompt:
        return {"music_prompt": music_prompt}
    return {"music_prompt": music_prompt, **MUSIC_RESET}


def is_assembly_change(episode: Episode, values: Mapping[str, Any]) -> bool:
    return any(
        name in values and values[name] != getattr(episode, name) for name in ASSEMBLY_FIELDS
    )
