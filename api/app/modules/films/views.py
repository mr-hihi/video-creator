from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.films.models import (
    Character,
    Episode,
    EpisodePart,
    FilmProject,
    Scene,
)
from app.modules.media_generation.models import GenerationRequest, GenerationStatus

CUT_HEAD_S = 1


@dataclass(frozen=True)
class ProjectSummary:
    project: FilmProject
    style_name: str
    episode_count: int


@dataclass(frozen=True)
class CharacterSummary:
    character: Character
    style_name: str
    project_count: int


@dataclass(frozen=True)
class ProjectLink:
    id: str
    name: str


@dataclass(frozen=True)
class CharacterDetail:
    summary: CharacterSummary
    projects: Sequence[ProjectLink]


@dataclass(frozen=True)
class EpisodeSummary:
    episode: Episode


@dataclass(frozen=True)
class ProjectDetail:
    summary: ProjectSummary
    characters: Sequence[CharacterSummary]
    episodes: Sequence[EpisodeSummary]
    is_look_fixed: bool
    open_requests: Sequence[GenerationRequest]


@dataclass(frozen=True)
class ThumbnailCandidate:
    candidate: int
    status: GenerationStatus
    path: str | None
    error_message: str | None


@dataclass(frozen=True)
class PartCounts:
    scene_count: int
    images_done: int
    clips_done: int
    narration_done: int
    narration_with_text: int
    failed_count: int
    open_request_count: int


@dataclass(frozen=True)
class PartSummary:
    part: EpisodePart
    counts: PartCounts


@dataclass(frozen=True)
class PartDetail:
    part: EpisodePart
    scenes: Sequence[Scene]
    open_requests: Sequence[GenerationRequest]


@dataclass(frozen=True)
class EpisodeDetail:
    summary: EpisodeSummary
    project: FilmProject
    parts: Sequence[PartSummary]
    open_requests: Sequence[GenerationRequest]
    thumbnail_candidates: Sequence[ThumbnailCandidate]
    is_source_deleted: bool
