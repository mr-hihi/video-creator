from dataclasses import dataclass

from app.modules.films.errors import (
    CharacterNotFoundError,
    EpisodeNotFoundError,
    EpisodeRunningError,
    FilmProjectNotFoundError,
    PartNotFoundError,
    ProjectArchivedError,
    SceneNotFoundError,
)
from app.modules.films.models import (
    Character,
    Episode,
    EpisodePart,
    EpisodeStatus,
    FilmProject,
    ProjectStatus,
    Scene,
)
from app.modules.films.repository import FilmRepository


@dataclass(frozen=True)
class EpisodeContext:
    project: FilmProject
    episode: Episode


@dataclass(frozen=True)
class PartContext:
    project: FilmProject
    episode: Episode
    part: EpisodePart


@dataclass(frozen=True)
class SceneContext:
    project: FilmProject
    episode: Episode
    scene: Scene


class FilmAccess:
    def __init__(self, repository: FilmRepository):
        self._repository = repository

    def get_project(self, project_id: str) -> FilmProject:
        project = self._repository.find_project(project_id)
        if project is None:
            raise FilmProjectNotFoundError(project_id)
        return project

    def get_active_project(self, project_id: str) -> FilmProject:
        project = self.get_project(project_id)
        ensure_project_active(project)
        return project

    def get_character(self, character_id: str) -> Character:
        character = self._repository.find_character(character_id)
        if character is None:
            raise CharacterNotFoundError(character_id)
        return character

    def get_episode(self, episode_id: str) -> EpisodeContext:
        episode = self._repository.find_episode(episode_id)
        if episode is None:
            raise EpisodeNotFoundError(episode_id)
        return EpisodeContext(project=self.get_project(episode.project_id), episode=episode)

    def get_writable_episode(self, episode_id: str) -> EpisodeContext:
        context = self.get_episode(episode_id)
        ensure_project_active(context.project)
        return context

    def get_editable_episode(self, episode_id: str) -> EpisodeContext:
        context = self.get_writable_episode(episode_id)
        ensure_not_running(context.episode)
        return context

    def get_part(self, part_id: str) -> PartContext:
        part = self._repository.find_part(part_id)
        if part is None:
            raise PartNotFoundError(part_id)
        context = self.get_episode(part.episode_id)
        return PartContext(project=context.project, episode=context.episode, part=part)

    def get_writable_part(self, part_id: str) -> PartContext:
        context = self.get_part(part_id)
        ensure_project_active(context.project)
        return context

    def get_editable_part(self, part_id: str) -> PartContext:
        context = self.get_writable_part(part_id)
        ensure_not_running(context.episode)
        return context

    def get_scene(self, scene_id: str) -> SceneContext:
        scene = self._repository.find_scene(scene_id)
        if scene is None:
            raise SceneNotFoundError(scene_id)
        context = self.get_episode(scene.episode_id)
        return SceneContext(project=context.project, episode=context.episode, scene=scene)

    def get_editable_scene(self, scene_id: str) -> SceneContext:
        context = self.get_scene(scene_id)
        ensure_project_active(context.project)
        ensure_not_running(context.episode)
        return context


def ensure_project_active(project: FilmProject) -> None:
    if project.status is ProjectStatus.ARCHIVED:
        raise ProjectArchivedError(project.id)


def ensure_not_running(episode: Episode) -> None:
    if episode.status is EpisodeStatus.RUNNING:
        raise EpisodeRunningError(episode.number)
