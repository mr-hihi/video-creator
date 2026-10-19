from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.modules.films.errors import FilmConflictError, PartNotFoundError
from app.modules.films.film_access import FilmAccess
from app.modules.films.models import EpisodePart, EpisodeStatus, MediaStatus, Scene
from app.modules.films.part_rules import (
    to_part_number,
    to_valid_part_duration,
    to_valid_part_plan,
    to_valid_part_title,
)
from app.modules.films.repository import FilmRepository
from app.modules.films.scene_rules import to_insert_position, to_valid_position
from app.modules.films.views import PartCounts, PartDetail
from app.modules.media_generation.models import GenerationRequest

PART_HAS_SCENES_MESSAGE = "Part {number} has scenes — delete them first"


@dataclass(frozen=True)
class PartDraft:
    after_position: int | None
    title: str
    plan: str
    target_duration_s: int


def to_part_counts(
    scenes: Sequence[Scene], open_requests: Sequence[GenerationRequest]
) -> PartCounts:
    scene_ids = {scene.id for scene in scenes}
    return PartCounts(
        scene_count=len(scenes),
        images_done=sum(1 for scene in scenes if scene.image_status is MediaStatus.DONE),
        clips_done=sum(1 for scene in scenes if scene.clip_status is MediaStatus.DONE),
        narration_done=sum(1 for scene in scenes if scene.narration_status is MediaStatus.DONE),
        narration_with_text=sum(1 for scene in scenes if (scene.narrator_text or "").strip()),
        failed_count=sum(1 for scene in scenes if _has_failed_media(scene)),
        open_request_count=sum(1 for request in open_requests if request.scene_id in scene_ids),
    )


def _has_failed_media(scene: Scene) -> bool:
    return MediaStatus.FAILED in (scene.image_status, scene.clip_status, scene.narration_status)


class PartService:
    def __init__(self, repository: FilmRepository, access: FilmAccess):
        self._repository = repository
        self._access = access

    def add_part(self, episode_id: str, draft: PartDraft) -> EpisodePart:
        self._access.get_editable_episode(episode_id)
        part = EpisodePart(
            id=str(uuid4()),
            episode_id=episode_id,
            position=to_insert_position(
                draft.after_position, len(self._repository.find_parts(episode_id))
            ),
            title=to_valid_part_title(draft.title),
            plan=to_valid_part_plan(draft.plan),
            target_duration_s=to_valid_part_duration(draft.target_duration_s),
            recap=None,
        )
        self._repository.insert_part(part)
        return self._reload(part.id)

    def get_part_detail(self, part_id: str) -> PartDetail:
        part = self._access.get_part(part_id).part
        scenes = self._repository.find_part_scenes(part.id)
        scene_ids = {scene.id for scene in scenes}
        return PartDetail(
            part=part,
            scenes=scenes,
            open_requests=[
                request
                for request in self._repository.find_open_requests_for_episode(part.episode_id)
                if request.scene_id in scene_ids
            ],
        )

    def update_part(self, part_id: str, changes: Mapping[str, Any]) -> EpisodePart:
        context = self._access.get_editable_part(part_id)
        values = to_part_values(changes)
        new_position = self._to_new_position(context.part, changes)
        if values:
            self._repository.update_part(part_id, values)
        if new_position is not None:
            self._repository.move_part(context.part, new_position)
            if context.episode.status is EpisodeStatus.DONE:
                self._repository.update_episode(context.episode.id, {"needs_assembly": True})
        return self._reload(part_id)

    def delete_part(self, part_id: str) -> None:
        context = self._access.get_editable_part(part_id)
        if self._repository.count_scenes_by_part([part_id]).get(part_id, 0):
            raise FilmConflictError(
                PART_HAS_SCENES_MESSAGE.format(number=to_part_number(context.part.position))
            )
        self._repository.delete_part(context.part)

    def _to_new_position(self, part: EpisodePart, changes: Mapping[str, Any]) -> int | None:
        position = changes.get("position")
        if position is None:
            return None
        part_count = len(self._repository.find_parts(part.episode_id))
        valid_position = to_valid_position(position, part_count)
        return None if valid_position == part.position else valid_position

    def _reload(self, part_id: str) -> EpisodePart:
        part = self._repository.find_part(part_id)
        if part is None:
            raise PartNotFoundError(part_id)
        return part


def to_part_values(changes: Mapping[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if "title" in changes:
        values["title"] = to_valid_part_title(changes["title"])
    if "plan" in changes:
        values["plan"] = to_valid_part_plan(changes["plan"])
    if "target_duration_s" in changes:
        values["target_duration_s"] = to_valid_part_duration(changes["target_duration_s"])
    return values
