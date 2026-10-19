import copy
import sys
from collections import Counter
from collections.abc import Collection, Mapping
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, call

import pytest
from sqlalchemy import inspect

from app.common.process import Command
from app.db import utc_now
from app.modules.films.errors import EpisodeStepFailedError, FilmConflictError
from app.modules.films.film_access import EpisodeContext, PartContext
from app.modules.films.film_files import FilmFiles
from app.modules.films.generation_targets import FilmTargetTools, build_film_targets
from app.modules.films.media_queue import FilmMediaQueue, SceneOrderContext
from app.modules.films.models import (
    Character,
    EntityType,
    Episode,
    EpisodePart,
    EpisodeSource,
    EpisodeStatus,
    EpisodeStep,
    FilmLanguage,
    FilmProject,
    MediaStatus,
    Orientation,
    ProjectStatus,
    Scene,
    Style,
)
from app.modules.films.stage_runner import (
    AssembledFilm,
    EpisodeAssembler,
    EpisodeStageRunner,
    OutlineWriter,
    ScriptWriter,
    StageRunnerTools,
    StoryBibleUpdater,
)
from app.modules.films.step_commands import EpisodeStepCommands
from app.modules.films.step_worker import EpisodeStepRunner, EpisodeStepTools
from app.modules.media_generation.models import (
    OPEN_GENERATION_STATUSES,
    GenerationKind,
    GenerationRequest,
    GenerationStatus,
)
from app.modules.media_generation.service import GenerationService
from app.modules.providers.provider_catalog import ProviderId

UPLOAD_MAX_MB = 20
CLIP_DURATION_MS = 8000
MAX_WORKER_ROUNDS = 50
CONTENT_FILTER_MESSAGE = "Blocked by the content filter"
FILM = AssembledFilm("projects/p1/episodes/e1/output/film.mp4", None, 21000)
EXTENSIONS_BY_KIND = {
    GenerationKind.CHARACTER_IMAGE: "png",
    GenerationKind.SCENE_IMAGE: "png",
    GenerationKind.EDIT_IMAGE: "png",
    GenerationKind.SCENE_CLIP: "mp4",
    GenerationKind.NARRATION: "mp3",
    GenerationKind.MUSIC: "mp3",
}
ALL_STOP_POINTS = {
    "afterOutline": True,
    "afterScript": True,
    "afterReferences": True,
    "afterSceneImages": True,
}
NO_STOP_POINTS = {
    "afterOutline": False,
    "afterScript": False,
    "afterReferences": False,
    "afterSceneImages": False,
}
STOP_POINTS_FROM_SCRIPT = {**ALL_STOP_POINTS, "afterOutline": False}


def detached_copy[RowT](row: RowT) -> RowT:
    attribute_keys = [attribute.key for attribute in inspect(type(row)).column_attrs]
    return type(row)(**{key: copy.deepcopy(getattr(row, key)) for key in attribute_keys})


def assign(row: Any, values: Mapping[str, Any]) -> None:
    for name, value in values.items():
        setattr(row, name, value)


class InMemoryFilmRepository:
    def __init__(self, requests: list[GenerationRequest]):
        self.projects: dict[str, FilmProject] = {}
        self.episodes: dict[str, Episode] = {}
        self.parts: dict[str, EpisodePart] = {}
        self.characters: dict[str, Character] = {}
        self.scenes: dict[str, Scene] = {}
        self.styles: dict[str, Style] = {}
        self.requests = requests

    def find_project(self, project_id: str) -> FilmProject | None:
        return self._copy_of(self.projects.get(project_id))

    def find_style(self, style_id: str) -> Style | None:
        return self._copy_of(self.styles.get(style_id))

    def find_voice(self, voice_id: str) -> None:
        return None

    def find_episode(self, episode_id: str) -> Episode | None:
        return self._copy_of(self.episodes.get(episode_id))

    def update_episode(self, episode_id: str, values: Mapping[str, Any]) -> None:
        assign(self.episodes[episode_id], values)

    def find_running_episodes(self, steps: Collection[EpisodeStep]) -> list[Episode]:
        return [
            detached_copy(episode)
            for episode in self.episodes.values()
            if episode.status is EpisodeStatus.RUNNING and episode.step in steps
        ]

    def find_running_episodes_of_project(self, project_id: str) -> list[Episode]:
        return [
            detached_copy(episode)
            for episode in self.episodes.values()
            if episode.project_id == project_id and episode.status is EpisodeStatus.RUNNING
        ]

    def find_parts(self, episode_id: str) -> list[EpisodePart]:
        parts = [part for part in self.parts.values() if part.episode_id == episode_id]
        return [detached_copy(part) for part in sorted(parts, key=lambda p: p.position)]

    def count_scenes_by_part(self, part_ids: Collection[str]) -> dict[str, int]:
        return dict(
            Counter(scene.part_id for scene in self.scenes.values() if scene.part_id in part_ids)
        )

    def find_scenes(self, episode_id: str) -> list[Scene]:
        scenes = [scene for scene in self.scenes.values() if scene.episode_id == episode_id]
        return [
            detached_copy(scene)
            for scene in sorted(scenes, key=lambda s: (self.parts[s.part_id].position, s.position))
        ]

    def find_part_scenes(self, part_id: str) -> list[Scene]:
        scenes = [scene for scene in self.scenes.values() if scene.part_id == part_id]
        return [detached_copy(scene) for scene in sorted(scenes, key=lambda s: s.position)]

    def find_scene(self, scene_id: str) -> Scene | None:
        return self._copy_of(self.scenes.get(scene_id))

    def update_scene(self, scene_id: str, values: Mapping[str, Any]) -> None:
        assign(self.scenes[scene_id], values)

    def delete_script(self, episode_id: str) -> None:
        for scene in self.find_scenes(episode_id):
            del self.scenes[scene.id]
        for part in self.find_parts(episode_id):
            del self.parts[part.id]

    def clear_part_script(self, part_id: str) -> None:
        for scene in self.find_part_scenes(part_id):
            del self.scenes[scene.id]
        self.parts[part_id].recap = None

    def find_character(self, character_id: str) -> Character | None:
        return self._copy_of(self.characters.get(character_id))

    def find_characters_by_ids(self, character_ids: Collection[str]) -> dict[str, Character]:
        return {
            character_id: detached_copy(self.characters[character_id])
            for character_id in character_ids
            if character_id in self.characters
        }

    def update_character(self, character_id: str, values: Mapping[str, Any]) -> None:
        assign(self.characters[character_id], values)

    def find_open_requests_for_episode(self, episode_id: str) -> list[GenerationRequest]:
        return [
            request
            for request in self.requests
            if request.episode_id == episode_id and request.status in OPEN_GENERATION_STATUSES
        ]

    def _copy_of[RowT](self, row: RowT | None) -> RowT | None:
        return None if row is None else detached_copy(row)


class InMemoryRequestRepository:
    def __init__(self, requests: list[GenerationRequest]):
        self.requests = requests

    def add(self, request: GenerationRequest) -> GenerationRequest:
        request.created_at = utc_now() + timedelta(microseconds=len(self.requests))
        self.requests.append(request)
        return request

    def find_by_id(self, request_id: str) -> GenerationRequest | None:
        return next((request for request in self.requests if request.id == request_id), None)

    def update_fields(self, request_id: str, values: Mapping[str, Any]) -> None:
        assign(self.find_by_id(request_id), values)

    def cancel_queued(self, request_ids: Collection[str]) -> int:
        cancelled = [
            request
            for request in self.requests
            if request.id in request_ids and request.status is GenerationStatus.QUEUED
        ]
        for request in cancelled:
            request.status = GenerationStatus.CANCELLED
        return len(cancelled)


class FakeProvider:
    def __init__(self, world: "FilmWorld"):
        self._world = world
        self.answers_by_kind: dict[GenerationKind, str] = {}
        self.answers_by_scene_id: dict[str, str] = {}

    def run_ready(self) -> bool:
        has_progressed = False
        for request in self._world.find_requests(GenerationStatus.QUEUED):
            target = self._world.targets[request.kind]
            if request.status is not GenerationStatus.QUEUED or not target.is_ready(request):
                continue
            answer = self._pick_answer(request)
            if answer == "wait":
                continue
            has_progressed = True
            request.status = GenerationStatus.PROCESSING
            target.mark_processing(request)
            self.answer(request, answer)
        return has_progressed

    def answer(self, request: GenerationRequest, answer: str) -> None:
        if answer == "done":
            self._finish_done(request)
        elif answer == "fail":
            self._finish_failed(request)

    def _pick_answer(self, request: GenerationRequest) -> str:
        if request.scene_id in self.answers_by_scene_id:
            return self.answers_by_scene_id[request.scene_id]
        return self.answers_by_kind.get(request.kind, "done")

    def _finish_done(self, request: GenerationRequest) -> None:
        target = self._world.targets[request.kind]
        output_path = target.output_path(request, EXTENSIONS_BY_KIND[request.kind])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"media")
        assign(request, {"status": GenerationStatus.DONE, "output_path": str(output_path)})
        target.save_result(request, output_path)
        target.on_final(request)

    def _finish_failed(self, request: GenerationRequest) -> None:
        target = self._world.targets[request.kind]
        assign(
            request,
            {
                "status": GenerationStatus.FAILED,
                "error_message": CONTENT_FILTER_MESSAGE,
                "attempts": 1,
            },
        )
        target.mark_failed(request, CONTENT_FILTER_MESSAGE)
        target.on_final(request)


class FilmWorld:
    def __init__(self, tmp_path: Path):
        self.requests: list[GenerationRequest] = []
        self.repository = InMemoryFilmRepository(self.requests)
        self.request_repository = InMemoryRequestRepository(self.requests)
        self.files = FilmFiles(tmp_path, UPLOAD_MAX_MB)
        duration_probe = MagicMock()
        duration_probe.probe_duration_ms.return_value = CLIP_DURATION_MS
        self.targets = build_film_targets(
            FilmTargetTools(
                repository=self.repository,
                files=self.files,
                request_repository=self.request_repository,
                duration_probe=duration_probe,
                on_final=lambda request: self.stage_runner.on_request_final(request),
            )
        )
        provider_service = MagicMock()
        provider_service.pick_provider.return_value = ProviderId.GOOGLE_FLOW.value
        generation_service = GenerationService(
            self.request_repository, provider_service, self.targets, MagicMock()
        )
        self.media_queue = FilmMediaQueue(
            self.repository, self.files, generation_service, lambda: ProviderId.ELEVENLABS
        )
        self.notify_step_worker = MagicMock()
        self.step_commands = EpisodeStepCommands()
        self.stage_runner = EpisodeStageRunner(
            StageRunnerTools(
                repository=self.repository,
                files=self.files,
                media_queue=self.media_queue,
                generation_service=generation_service,
                notify_step_worker=self.notify_step_worker,
                cancel_worker_step=self.step_commands.cancel,
            )
        )
        self.outline_writer = MagicMock(spec=OutlineWriter)
        self.outline_writer.write_outline.side_effect = self._write_outline
        self.written_parts: list[EpisodePart] = []
        self.script_writer = MagicMock(spec=ScriptWriter)
        self.script_writer.write_part.side_effect = self._write_part
        self.script_failures: list[Exception] = []
        self.written_scenes: list[Scene] = []
        self.story_bible_updater = MagicMock(spec=StoryBibleUpdater)
        self.assembler = MagicMock(spec=EpisodeAssembler)
        self.assembler.assemble.return_value = FILM
        self.step_worker = EpisodeStepRunner(
            EpisodeStepTools(
                repository=self.repository,
                stage_runner=self.stage_runner,
                outline_writer=self.outline_writer,
                script_writer=self.script_writer,
                story_bible_updater=self.story_bible_updater,
                assembler=self.assembler,
                commands=self.step_commands,
            )
        )
        self.provider = FakeProvider(self)

    def add(self, *rows: Any) -> None:
        stores = {
            FilmProject: self.repository.projects,
            Episode: self.repository.episodes,
            EpisodePart: self.repository.parts,
            Character: self.repository.characters,
            Scene: self.repository.scenes,
            Style: self.repository.styles,
        }
        for row in rows:
            stores[type(row)][row.id] = row

    def context(self, episode_id: str = "e1") -> EpisodeContext:
        episode = self.repository.find_episode(episode_id)
        return EpisodeContext(self.repository.find_project(episode.project_id), episode)

    def part_context(self, part_id: str) -> PartContext:
        episode_context = self.context()
        return PartContext(
            episode_context.project, episode_context.episode, detached_copy(self.part(part_id))
        )

    def run_until_idle(self) -> None:
        for _ in range(MAX_WORKER_ROUNDS):
            has_progressed = self.step_worker.run_next(lambda: False)
            has_progressed = self.provider.run_ready() or has_progressed
            if not has_progressed:
                return

    def find_requests(
        self, status: GenerationStatus | None = None, kind: GenerationKind | None = None
    ) -> list[GenerationRequest]:
        return [
            request
            for request in self.requests
            if (status is None or request.status is status)
            and (kind is None or request.kind is kind)
        ]

    def episode(self, episode_id: str = "e1") -> Episode:
        return self.repository.episodes[episode_id]

    def scene(self, scene_id: str) -> Scene:
        return self.repository.scenes[scene_id]

    def part(self, part_id: str) -> EpisodePart:
        return self.repository.parts[part_id]

    def scene_ids_by_part(self) -> list[tuple[str, str]]:
        return [(scene.part_id, scene.id) for scene in self.repository.find_scenes("e1")]

    def _write_outline(self, episode_id: str) -> None:
        self.add(*(detached_copy(part) for part in self.written_parts))

    def _write_part(self, part_id: str) -> None:
        if self.script_failures:
            raise self.script_failures.pop(0)
        self.add(
            *(detached_copy(scene) for scene in self.written_scenes if scene.part_id == part_id)
        )


def build_project(**values) -> FilmProject:
    defaults = {
        "id": "p1",
        "name": "Test Series",
        "language": FilmLanguage.ENGLISH,
        "orientation": Orientation.LANDSCAPE,
        "style_id": "realistic",
        "clip_duration_s": 8,
        "allow_dialogue": True,
        "allow_narration": False,
        "narrator_voice_id": None,
        "allow_music": False,
        "status": ProjectStatus.ACTIVE,
        "last_episode_number": 1,
    }
    return FilmProject(**{**defaults, **values})


def build_style() -> Style:
    return Style(
        id="realistic",
        name="Photorealistic",
        style_instruction="Photorealistic photo.",
        negative_prompt=None,
        scene_prefix=None,
        lighting="Studio lighting",
    )


def build_episode(**values) -> Episode:
    defaults = {
        "id": "e1",
        "project_id": "p1",
        "number": 1,
        "title": "Episode 1",
        "source": EpisodeSource.IDEA,
        "idea": "A storm",
        "target_duration_s": 21,
        "stop_points": NO_STOP_POINTS,
        "paused_stop_point": None,
        "music_prompt": None,
        "music_status": MediaStatus.NONE,
        "music_path": None,
        "status": EpisodeStatus.DRAFT,
        "step": None,
        "error_message": None,
        "needs_assembly": False,
        "video_path": None,
        "started_at": None,
        "finished_at": None,
    }
    return Episode(**{**defaults, **values})


def build_part(part_id: str, position: int, **values) -> EpisodePart:
    defaults = {
        "id": part_id,
        "episode_id": "e1",
        "position": position,
        "title": f"Part {position + 1}",
        "plan": f"{part_id} plan",
        "target_duration_s": 21,
        "recap": None,
    }
    return EpisodePart(**{**defaults, **values})


def build_character(character_id: str, name: str, **values) -> Character:
    defaults = {
        "id": character_id,
        "name": name,
        "entity_type": EntityType.CHARACTER,
        "image_prompt": f"Reference image of {name}.",
        "voice_description": None,
        "reference_status": MediaStatus.NONE,
        "reference_path": None,
    }
    return Character(**{**defaults, **values})


def build_scene(scene_id: str, position: int, **values) -> Scene:
    defaults = {
        "id": scene_id,
        "episode_id": "e1",
        "part_id": "pt0",
        "position": position,
        "image_prompt": f"{scene_id} image",
        "video_prompt": f"{scene_id} video",
        "narrator_text": None,
        "character_ids": [],
        "image_status": MediaStatus.NONE,
        "clip_status": MediaStatus.NONE,
        "narration_status": MediaStatus.NONE,
        "image_path": None,
        "clip_path": None,
        "narration_path": None,
        "clip_duration_ms": None,
        "trim_start_ms": 1000,
        "trim_end_ms": None,
    }
    return Scene(**{**defaults, **values})


def build_done_image_scene(scene_id: str, position: int, **values) -> Scene:
    return build_scene(
        scene_id,
        position,
        image_status=MediaStatus.DONE,
        image_path=f"projects/p1/episodes/e1/scenes/{scene_id}/image.png",
        **values,
    )


def build_world(tmp_path, episode: Episode | None = None, project: FilmProject | None = None):
    world = FilmWorld(tmp_path)
    world.add(project or build_project(), build_style(), episode or build_episode())
    return world


def snapshot(world: FilmWorld) -> tuple:
    episode = world.episode()
    return (episode.status, episode.step)


def describe_requests(world: FilmWorld, kind: GenerationKind) -> list[tuple]:
    return [
        (request.scene_id or request.character_id, request.status)
        for request in world.find_requests(kind=kind)
    ]


def capture_conflict(action) -> str:
    with pytest.raises(FilmConflictError) as error:
        action()
    return str(error.value)


@pytest.fixture
def status_rules(tmp_path):
    world = build_world(tmp_path)
    world.add(build_part("pt0", 0), build_scene("s1", 0))
    continue_from_draft = capture_conflict(
        lambda: world.stage_runner.continue_episode(world.context())
    )
    started = world.stage_runner.start(world.context())
    start_again = capture_conflict(lambda: world.stage_runner.start(world.context()))
    assemble_running = capture_conflict(lambda: world.stage_runner.assemble(world.context()))
    rewrite_running = capture_conflict(lambda: world.stage_runner.rewrite_script(world.context()))
    stopped = world.stage_runner.stop(world.context())
    world.repository.projects["p1"].allow_narration = True
    continue_without_voice = capture_conflict(
        lambda: world.stage_runner.continue_episode(world.context())
    )
    return SimpleNamespace(
        continue_from_draft=continue_from_draft,
        started=started,
        start_again=start_again,
        assemble_running=assemble_running,
        rewrite_running=rewrite_running,
        stopped=stopped,
        continue_without_voice=continue_without_voice,
        world=world,
    )


def test_continue_is_refused_from_draft(status_rules):
    assert status_rules.continue_from_draft == "Cannot continue episode 1 while it is draft"


def test_start_runs_from_writing_the_outline(status_rules):
    assert (
        status_rules.started.status,
        status_rules.started.step,
        status_rules.started.started_at is not None,
    ) == (EpisodeStatus.RUNNING, EpisodeStep.WRITING_OUTLINE, True)


def test_start_wakes_the_step_worker(status_rules):
    status_rules.world.notify_step_worker.assert_called_once_with()


def test_start_is_refused_while_running(status_rules):
    assert status_rules.start_again == "Cannot start episode 1 while it is running"


def test_assemble_is_refused_while_running(status_rules):
    assert status_rules.assemble_running == "Cannot assemble episode 1 while it is running"


def test_rewrite_is_refused_while_running(status_rules):
    assert status_rules.rewrite_running == (
        "Cannot rewrite the script of episode 1 while it is running"
    )


def test_stop_pauses_at_once_and_keeps_the_step(status_rules):
    assert (status_rules.stopped.status, status_rules.stopped.step) == (
        EpisodeStatus.PAUSED,
        EpisodeStep.WRITING_OUTLINE,
    )


def test_continue_needs_a_narrator_when_narration_is_on(status_rules):
    assert status_rules.continue_without_voice == (
        "Pick a narrator voice for the project or turn narration off"
    )


@pytest.fixture
def blocked_rewrite(tmp_path):
    world = build_world(
        tmp_path,
        build_episode(status=EpisodeStatus.FAILED, step=EpisodeStep.GENERATING_CLIPS),
    )
    world.add(build_part("pt0", 0), build_done_image_scene("s1", 0), build_scene("s2", 1))
    message = capture_conflict(lambda: world.stage_runner.rewrite_script(world.context()))
    return SimpleNamespace(
        message=message,
        part_ids=sorted(world.repository.parts),
        scene_ids=sorted(world.repository.scenes),
    )


def test_rewrite_is_refused_once_a_scene_has_an_image(blocked_rewrite):
    assert blocked_rewrite.message == (
        "Scenes already have images or clips — delete them before rewriting"
    )


def test_a_refused_rewrite_keeps_the_parts_and_scenes(blocked_rewrite):
    assert (blocked_rewrite.part_ids, blocked_rewrite.scene_ids) == (["pt0"], ["s1", "s2"])


@pytest.fixture
def rewrite_with_open_request(tmp_path):
    world = build_world(
        tmp_path,
        build_episode(status=EpisodeStatus.PAUSED, step=EpisodeStep.GENERATING_SCENE_IMAGES),
    )
    world.add(build_part("pt0", 0), build_scene("s1", 0))
    world.requests.append(
        GenerationRequest(
            id="r1",
            kind=GenerationKind.SCENE_IMAGE,
            episode_id="e1",
            scene_id="s1",
            status=GenerationStatus.PROCESSING,
        )
    )
    message = capture_conflict(lambda: world.stage_runner.rewrite_script(world.context()))
    return SimpleNamespace(message=message, scene_ids=sorted(world.repository.scenes))


def test_rewrite_is_refused_while_a_request_is_open(rewrite_with_open_request):
    assert rewrite_with_open_request.message == "Episode 1 has generation running"
    assert rewrite_with_open_request.scene_ids == ["s1"]


@pytest.fixture
def rewritten_episode(tmp_path):
    world = build_world(
        tmp_path,
        build_episode(status=EpisodeStatus.PAUSED, step=EpisodeStep.WRITING_SCRIPT),
    )
    scene_dir = world.files.scene_dir("p1", "e1", "s1")
    scene_dir.mkdir(parents=True)
    world.add(build_part("pt0", 0), build_scene("s1", 0))
    episode = world.stage_runner.rewrite_script(world.context())
    return SimpleNamespace(episode=episode, world=world, scene_dir=scene_dir)


def test_rewrite_deletes_the_parts_and_scenes_and_writes_the_outline_again(rewritten_episode):
    assert (
        rewritten_episode.episode.status,
        rewritten_episode.episode.step,
        rewritten_episode.world.repository.parts,
        rewritten_episode.world.repository.scenes,
        rewritten_episode.scene_dir.exists(),
    ) == (EpisodeStatus.RUNNING, EpisodeStep.WRITING_OUTLINE, {}, {}, False)


def test_rewrite_wakes_the_step_worker(rewritten_episode):
    rewritten_episode.world.notify_step_worker.assert_called_once_with()


@pytest.fixture
def archived_start(tmp_path):
    world = build_world(tmp_path, project=build_project(status=ProjectStatus.ARCHIVED))
    return capture_conflict(lambda: world.stage_runner.start(world.context()))


def test_an_archived_project_refuses_every_action(archived_start):
    assert archived_start == "Film project p1 is archived"


@pytest.fixture
def stop_point_run(tmp_path):
    world = build_world(tmp_path, build_episode(stop_points=ALL_STOP_POINTS))
    world.add(build_character("c1", "Mai"))
    world.written_parts = [build_part("pt0", 0)]
    world.written_scenes = [
        build_scene(f"s{index}", index, character_ids=["c1"]) for index in range(3)
    ]
    world.stage_runner.start(world.context())
    world.run_until_idle()
    after_outline = (
        snapshot(world),
        sorted(world.repository.parts),
        sorted(world.repository.scenes),
        list(world.requests),
    )
    world.stage_runner.continue_episode(world.context())
    world.run_until_idle()
    after_script = (
        snapshot(world),
        sorted(world.repository.scenes),
        world.story_bible_updater.update_story_bible.call_count,
        list(world.requests),
    )
    world.stage_runner.continue_episode(world.context())
    world.run_until_idle()
    after_references = (
        snapshot(world),
        world.story_bible_updater.update_story_bible.call_args_list,
        describe_requests(world, GenerationKind.CHARACTER_IMAGE),
    )
    world.stage_runner.continue_episode(world.context())
    world.run_until_idle()
    after_images = (snapshot(world), describe_requests(world, GenerationKind.SCENE_IMAGE))
    world.stage_runner.continue_episode(world.context())
    world.run_until_idle()
    return SimpleNamespace(
        after_outline=after_outline,
        after_script=after_script,
        after_references=after_references,
        after_images=after_images,
        clips=describe_requests(world, GenerationKind.SCENE_CLIP),
        episode=world.episode(),
        world=world,
    )


def test_the_run_pauses_after_the_outline_with_parts_and_nothing_else(stop_point_run):
    assert stop_point_run.after_outline == (
        (EpisodeStatus.PAUSED, EpisodeStep.WRITING_OUTLINE),
        ["pt0"],
        [],
        [],
    )


def test_continue_writes_the_scenes_and_pauses_before_the_story_bible(stop_point_run):
    assert stop_point_run.after_script == (
        (EpisodeStatus.PAUSED, EpisodeStep.WRITING_SCRIPT),
        ["s0", "s1", "s2"],
        0,
        [],
    )


def test_continue_updates_the_story_bible_then_pauses_after_references(stop_point_run):
    assert stop_point_run.after_references == (
        (EpisodeStatus.PAUSED, EpisodeStep.GENERATING_REFERENCES),
        [call("e1")],
        [("c1", GenerationStatus.DONE)],
    )


def test_continue_makes_every_scene_image_and_pauses_after_them(stop_point_run):
    assert stop_point_run.after_images == (
        (EpisodeStatus.PAUSED, EpisodeStep.GENERATING_SCENE_IMAGES),
        [
            ("s0", GenerationStatus.DONE),
            ("s1", GenerationStatus.DONE),
            ("s2", GenerationStatus.DONE),
        ],
    )


def test_the_last_continue_makes_the_clips(stop_point_run):
    assert stop_point_run.clips == [
        ("s0", GenerationStatus.DONE),
        ("s1", GenerationStatus.DONE),
        ("s2", GenerationStatus.DONE),
    ]


def test_the_last_continue_assembles_the_film(stop_point_run):
    episode = stop_point_run.episode
    assert (
        episode.status,
        episode.finished_at is not None,
        episode.needs_assembly,
        episode.video_path,
        episode.duration_ms,
    ) == (EpisodeStatus.DONE, True, False, FILM.video_path, FILM.duration_ms)


def test_the_outline_and_the_part_are_written_once(stop_point_run):
    assert (
        stop_point_run.world.outline_writer.write_outline.call_args_list,
        stop_point_run.world.script_writer.write_part.call_args_list,
    ) == ([call("e1")], [call("pt0")])


@pytest.fixture
def stopped_clip_run(tmp_path):
    world = build_world(
        tmp_path,
        build_episode(status=EpisodeStatus.PAUSED, step=EpisodeStep.GENERATING_CLIPS),
    )
    world.add(
        build_part("pt0", 0), *(build_done_image_scene(f"s{index}", index) for index in range(3))
    )
    world.provider.answers_by_scene_id = {"s0": "hold", "s1": "wait", "s2": "wait"}
    world.stage_runner.continue_episode(world.context())
    world.run_until_idle()
    first_clip = world.find_requests(kind=GenerationKind.SCENE_CLIP)[0]
    stopped = world.stage_runner.stop(world.context())
    after_stop = (
        [request.status for request in world.find_requests(kind=GenerationKind.SCENE_CLIP)],
        [world.scene(f"s{index}").clip_status for index in range(3)],
    )
    world.provider.answer(first_clip, "done")
    world.run_until_idle()
    after_release = (
        first_clip.status,
        world.scene("s0").clip_status,
        len(world.find_requests(kind=GenerationKind.SCENE_CLIP)),
        snapshot(world),
    )
    world.stage_runner.continue_episode(world.context())
    return SimpleNamespace(
        stopped=stopped,
        after_stop=after_stop,
        after_release=after_release,
        new_clips=[
            request.scene_id
            for request in world.find_requests(GenerationStatus.QUEUED, GenerationKind.SCENE_CLIP)
        ],
    )


def test_stop_pauses_at_the_running_stage(stopped_clip_run):
    assert (stopped_clip_run.stopped.status, stopped_clip_run.stopped.step) == (
        EpisodeStatus.PAUSED,
        EpisodeStep.GENERATING_CLIPS,
    )


def test_stop_cancels_queued_requests_and_frees_their_scenes(stopped_clip_run):
    assert stopped_clip_run.after_stop == (
        [GenerationStatus.PROCESSING, GenerationStatus.CANCELLED, GenerationStatus.CANCELLED],
        [MediaStatus.PROCESSING, MediaStatus.NONE, MediaStatus.NONE],
    )


def test_a_processing_request_finishes_after_stop_without_new_work(stopped_clip_run):
    assert stopped_clip_run.after_release == (
        GenerationStatus.DONE,
        MediaStatus.DONE,
        3,
        (EpisodeStatus.PAUSED, EpisodeStep.GENERATING_CLIPS),
    )


def test_continue_queues_only_the_cancelled_clips(stopped_clip_run):
    assert stopped_clip_run.new_clips == ["s1", "s2"]


@pytest.fixture
def failing_image_run(tmp_path):
    world = build_world(
        tmp_path,
        build_episode(status=EpisodeStatus.PAUSED, step=EpisodeStep.GENERATING_SCENE_IMAGES),
    )
    world.add(build_part("pt0", 0), *(build_scene(f"s{index}", index) for index in range(3)))
    world.provider.answers_by_scene_id = {"s0": "hold", "s1": "fail", "s2": "fail"}
    world.stage_runner.continue_episode(world.context())
    world.run_until_idle()
    while_held = (snapshot(world), [request.attempts for request in world.requests[1:]])
    world.provider.answer(world.requests[0], "done")
    after_failure = (snapshot(world), world.episode().error_message)
    world.provider.answers_by_scene_id = {}
    world.provider.answers_by_kind[GenerationKind.SCENE_CLIP] = "hold"
    request_count = len(world.requests)
    world.stage_runner.resume(world.context())
    world.run_until_idle()
    return SimpleNamespace(
        while_held=while_held,
        after_failure=after_failure,
        retried=[
            request.scene_id
            for request in world.requests[request_count:]
            if request.kind is GenerationKind.SCENE_IMAGE
        ],
        after_resume=snapshot(world),
    )


def test_failed_images_wait_for_the_running_one(failing_image_run):
    assert failing_image_run.while_held == (
        (EpisodeStatus.RUNNING, EpisodeStep.GENERATING_SCENE_IMAGES),
        [1, 1],
    )


def test_the_stage_fails_once_nothing_is_open(failing_image_run):
    assert failing_image_run.after_failure == (
        (EpisodeStatus.FAILED, EpisodeStep.GENERATING_SCENE_IMAGES),
        "2 scene image(s) failed — fix them and resume",
    )


def test_resume_queues_only_the_failed_images(failing_image_run):
    assert failing_image_run.retried == ["s1", "s2"]


def test_resume_moves_on_to_the_clips(failing_image_run):
    assert failing_image_run.after_resume == (
        EpisodeStatus.RUNNING,
        EpisodeStep.GENERATING_CLIPS,
    )


@pytest.fixture
def failed_script_run(tmp_path):
    world = build_world(tmp_path, build_episode(stop_points=STOP_POINTS_FROM_SCRIPT))
    world.written_parts = [build_part("pt0", 0)]
    world.written_scenes = [build_scene("s0", 0)]
    world.script_failures = [
        EpisodeStepFailedError("Part 1: claude returned output that is not JSON")
    ]
    world.stage_runner.start(world.context())
    world.run_until_idle()
    after_failure = (snapshot(world), world.episode().error_message, dict(world.repository.scenes))
    world.stage_runner.resume(world.context())
    world.run_until_idle()
    return SimpleNamespace(
        after_failure=after_failure,
        after_resume=snapshot(world),
        writer_calls=(
            world.outline_writer.write_outline.call_count,
            world.script_writer.write_part.call_count,
        ),
    )


@pytest.fixture
def stopped_script_step(tmp_path):
    world = build_world(tmp_path, build_episode(stop_points=ALL_STOP_POINTS))
    world.add(build_part("pt0", 0))
    world.written_scenes = [build_scene("s0", 0)]
    pending_stops = [True]

    def stop_once_while_claude_runs(part_id: str) -> None:
        if pending_stops:
            pending_stops.pop()
            world.stage_runner.stop(world.context())
            world.step_commands.run(Command(args=[sys.executable, "-c", "pass"], timeout_sec=10))
        world.add(*(detached_copy(scene) for scene in world.written_scenes))

    world.script_writer.write_part.side_effect = stop_once_while_claude_runs
    world.stage_runner.start(world.context())
    world.run_until_idle()
    after_outline = snapshot(world)
    world.stage_runner.continue_episode(world.context())
    world.run_until_idle()
    after_stop = (snapshot(world), world.episode().error_message, dict(world.repository.scenes))
    world.stage_runner.continue_episode(world.context())
    world.run_until_idle()
    return SimpleNamespace(
        after_outline=after_outline,
        after_stop=after_stop,
        after_continue=(
            world.outline_writer.write_outline.call_count,
            world.script_writer.write_part.call_count,
            list(world.repository.scenes),
            snapshot(world),
        ),
    )


def test_a_skipped_outline_still_pauses_at_its_stop_point(stopped_script_step):
    assert stopped_script_step.after_outline == (EpisodeStatus.PAUSED, EpisodeStep.WRITING_OUTLINE)


def test_stop_while_writing_drops_the_script_and_keeps_the_step(stopped_script_step):
    assert stopped_script_step.after_stop == (
        (EpisodeStatus.PAUSED, EpisodeStep.WRITING_SCRIPT),
        None,
        {},
    )


def test_continue_after_a_stopped_script_writes_it_again(stopped_script_step):
    assert stopped_script_step.after_continue == (
        0,
        2,
        ["s0"],
        (EpisodeStatus.PAUSED, EpisodeStep.WRITING_SCRIPT),
    )


def test_a_script_failure_fails_the_episode_without_scenes(failed_script_run):
    assert failed_script_run.after_failure == (
        (EpisodeStatus.FAILED, EpisodeStep.WRITING_SCRIPT),
        "Part 1: claude returned output that is not JSON",
        {},
    )


def test_resume_after_a_script_failure_calls_only_the_part_writer_again(failed_script_run):
    assert (failed_script_run.writer_calls, failed_script_run.after_resume) == (
        (1, 2),
        (EpisodeStatus.PAUSED, EpisodeStep.WRITING_SCRIPT),
    )


@pytest.fixture
def manual_screenplay_run(tmp_path):
    world = build_world(
        tmp_path,
        build_episode(
            stop_points={**NO_STOP_POINTS, "afterReferences": True, "afterSceneImages": True}
        ),
    )
    world.add(build_part("pt0", 0), build_scene("s0", 0), build_scene("s1", 1))
    world.stage_runner.start(world.context())
    world.run_until_idle()
    return SimpleNamespace(
        writer_calls=(
            world.outline_writer.write_outline.call_count,
            world.script_writer.write_part.call_count,
        ),
        story_bible_calls=world.story_bible_updater.update_story_bible.call_args_list,
        scene_ids=sorted(world.repository.scenes),
        state=snapshot(world),
    )


def test_a_manual_screenplay_skips_the_outline_and_part_calls(manual_screenplay_run):
    assert (
        manual_screenplay_run.writer_calls,
        manual_screenplay_run.scene_ids,
        manual_screenplay_run.state,
    ) == ((0, 0), ["s0", "s1"], (EpisodeStatus.PAUSED, EpisodeStep.GENERATING_REFERENCES))


def test_a_manual_screenplay_still_updates_the_story_bible(manual_screenplay_run):
    assert manual_screenplay_run.story_bible_calls == [call("e1")]


@pytest.fixture
def clone_episode_run(tmp_path):
    world = build_world(tmp_path, build_episode(source=EpisodeSource.FILM_CLONE))
    world.add(
        build_character("c-mai", "Mai", reference_status=MediaStatus.DONE, reference_path="x.png"),
        build_character("c-fan", "Fan", reference_status=MediaStatus.DONE, reference_path="y.png"),
        build_character("c-crowd", "Crowd"),
        build_part("pt0", 0, title="Part 1", plan="Scenes 1-2 of the film clone."),
        build_done_image_scene("s0", 0, character_ids=["c-mai", "c-fan"]),
        build_done_image_scene("s1", 1, character_ids=["c-crowd"]),
    )
    world.provider.answers_by_kind[GenerationKind.SCENE_CLIP] = "hold"
    world.stage_runner.start(world.context())
    world.run_until_idle()
    return SimpleNamespace(
        writer_calls=(
            world.outline_writer.write_outline.call_count,
            world.script_writer.write_part.call_count,
        ),
        story_bible_calls=world.story_bible_updater.update_story_bible.call_args_list,
        references=describe_requests(world, GenerationKind.CHARACTER_IMAGE),
        scene_images=world.find_requests(kind=GenerationKind.SCENE_IMAGE),
        state=snapshot(world),
    )


def test_a_clone_episode_never_calls_the_outline_or_part_writer(clone_episode_run):
    assert clone_episode_run.writer_calls == (0, 0)


def test_a_clone_episode_updates_the_story_bible_once(clone_episode_run):
    assert clone_episode_run.story_bible_calls == [call("e1")]


def test_a_clone_episode_makes_only_the_missing_reference(clone_episode_run):
    assert clone_episode_run.references == [("c-crowd", GenerationStatus.DONE)]


def test_a_clone_episode_skips_its_copied_scene_images(clone_episode_run):
    assert (clone_episode_run.scene_images, clone_episode_run.state) == (
        [],
        (EpisodeStatus.RUNNING, EpisodeStep.GENERATING_CLIPS),
    )


@pytest.fixture
def waiting_requests(tmp_path):
    world = build_world(tmp_path, build_episode(status=EpisodeStatus.PAUSED))
    world.add(
        build_character("c1", "Mai", reference_status=MediaStatus.DONE, reference_path="m.png"),
        build_part("pt0", 0),
        build_scene("s0", 0, character_ids=["c1"]),
        build_scene("s1", 1, image_status=MediaStatus.PROCESSING),
    )
    project = world.repository.find_project("p1")
    image_request = world.media_queue.queue_scene_image(
        SceneOrderContext(project, "e1", world.repository.find_scene("s0"))
    )
    clip_request = world.media_queue.queue_scene_clip(
        SceneOrderContext(project, "e1", world.repository.find_scene("s1"))
    )
    world.repository.characters["c1"].reference_status = MediaStatus.FAILED
    world.run_until_idle()
    while_image_processing = clip_request.status
    world.repository.scenes["s1"].image_status = MediaStatus.DONE
    world.run_until_idle()
    return SimpleNamespace(
        image_request=image_request,
        scene_image_status=world.scene("s0").image_status,
        while_image_processing=while_image_processing,
        clip_request=clip_request,
    )


def test_a_scene_image_without_its_references_fails_unsubmitted(waiting_requests):
    assert (
        waiting_requests.image_request.status,
        waiting_requests.image_request.error_message,
        waiting_requests.scene_image_status,
    ) == (GenerationStatus.FAILED, "Reference image missing for: Mai", MediaStatus.FAILED)


def test_a_clip_waits_for_its_scene_image(waiting_requests):
    assert (waiting_requests.while_image_processing, waiting_requests.clip_request.status) == (
        GenerationStatus.QUEUED,
        GenerationStatus.DONE,
    )


@pytest.fixture
def regenerated_images(tmp_path):
    world = build_world(tmp_path, build_episode(status=EpisodeStatus.PAUSED))
    world.add(build_part("pt0", 0), build_done_image_scene("s0", 0), build_scene("s1", 1))
    old_file = world.files.to_absolute(world.scene("s0").image_path)
    old_file.parent.mkdir(parents=True)
    old_file.write_bytes(b"file A")
    world.provider.answers_by_kind[GenerationKind.SCENE_IMAGE] = "fail"
    project = world.repository.find_project("p1")
    for scene_id in ("s0", "s1"):
        world.media_queue.queue_scene_image(
            SceneOrderContext(project, "e1", world.repository.find_scene(scene_id))
        )
    world.run_until_idle()
    return SimpleNamespace(
        regenerated=world.scene("s0"),
        first_try=world.scene("s1"),
        old_file=old_file,
    )


def test_a_failed_regenerate_keeps_the_old_image(regenerated_images):
    scene = regenerated_images.regenerated
    assert (
        scene.image_status,
        scene.image_error,
        regenerated_images.old_file.read_bytes(),
    ) == (MediaStatus.DONE, CONTENT_FILTER_MESSAGE, b"file A")


def test_a_failed_first_image_is_failed(regenerated_images):
    assert (
        regenerated_images.first_try.image_status,
        regenerated_images.first_try.image_error,
    ) == (
        MediaStatus.FAILED,
        CONTENT_FILTER_MESSAGE,
    )


@pytest.fixture
def stopped_image_stage(tmp_path):
    world = build_world(
        tmp_path,
        build_episode(status=EpisodeStatus.PAUSED, step=EpisodeStep.GENERATING_SCENE_IMAGES),
    )
    world.add(build_part("pt0", 0), build_scene("s0", 0))
    world.stage_runner.continue_episode(world.context())
    world.stage_runner.stop(world.context())
    return SimpleNamespace(
        request_status=world.requests[0].status, image_status=world.scene("s0").image_status
    )


def test_stop_cancels_a_queued_image_and_frees_its_scene(stopped_image_stage):
    assert (stopped_image_stage.request_status, stopped_image_stage.image_status) == (
        GenerationStatus.CANCELLED,
        MediaStatus.NONE,
    )


@pytest.fixture
def rewritten_part_run(tmp_path):
    world = build_world(
        tmp_path,
        build_episode(
            status=EpisodeStatus.PAUSED,
            step=EpisodeStep.GENERATING_SCENE_IMAGES,
            stop_points=STOP_POINTS_FROM_SCRIPT,
            paused_stop_point=EpisodeStep.WRITING_SCRIPT,
        ),
    )
    world.add(
        build_part("pt0", 0, recap="Mai dives."),
        build_part("pt1", 1, recap="Mai finds the city."),
        build_part("pt2", 2, recap="Mai escapes."),
        build_done_image_scene("s0", 0, part_id="pt0"),
        build_done_image_scene("s1", 1, part_id="pt0"),
        build_scene("s2", 0, part_id="pt1"),
        build_scene("s3", 1, part_id="pt1"),
        build_scene("s4", 0, part_id="pt2"),
        build_scene("s5", 1, part_id="pt2"),
    )
    world.written_scenes = [build_scene("s6", 0, part_id="pt1")]
    blocked_message = capture_conflict(
        lambda: world.stage_runner.rewrite_part(world.part_context("pt0"))
    )
    rewritten = world.stage_runner.rewrite_part(world.part_context("pt1"))
    after_rewrite = (snapshot(world), world.part("pt1").recap, world.scene_ids_by_part())
    world.run_until_idle()
    return SimpleNamespace(
        blocked_message=blocked_message,
        rewritten=(rewritten.status, rewritten.step, rewritten.paused_stop_point),
        after_rewrite=after_rewrite,
        written_parts=world.script_writer.write_part.call_args_list,
        scene_ids_by_part=world.scene_ids_by_part(),
        state=snapshot(world),
    )


def test_rewrite_part_is_refused_for_a_part_whose_scenes_have_images(rewritten_part_run):
    assert rewritten_part_run.blocked_message == (
        "Part 1 already has images or clips — delete them before rewriting"
    )


def test_rewrite_part_clears_only_that_part_and_runs_the_script_step(rewritten_part_run):
    assert (rewritten_part_run.rewritten, rewritten_part_run.after_rewrite) == (
        (EpisodeStatus.RUNNING, EpisodeStep.WRITING_SCRIPT, None),
        (
            (EpisodeStatus.RUNNING, EpisodeStep.WRITING_SCRIPT),
            None,
            [("pt0", "s0"), ("pt0", "s1"), ("pt2", "s4"), ("pt2", "s5")],
        ),
    )


def test_rewrite_part_writes_only_that_part_and_keeps_the_others(rewritten_part_run):
    assert (rewritten_part_run.written_parts, rewritten_part_run.scene_ids_by_part) == (
        [call("pt1")],
        [("pt0", "s0"), ("pt0", "s1"), ("pt1", "s6"), ("pt2", "s4"), ("pt2", "s5")],
    )


def test_rewrite_part_pauses_again_after_the_script(rewritten_part_run):
    assert rewritten_part_run.state == (EpisodeStatus.PAUSED, EpisodeStep.WRITING_SCRIPT)
