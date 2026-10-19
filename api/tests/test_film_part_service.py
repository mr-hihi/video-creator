from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, call

import pytest

from app.modules.films.errors import (
    EpisodeRunningError,
    FilmConflictError,
    FilmNotFoundError,
    InvalidFilmRequestError,
)
from app.modules.films.film_access import FilmAccess
from app.modules.films.models import (
    Episode,
    EpisodePart,
    EpisodeSource,
    EpisodeStatus,
    FilmProject,
    MediaStatus,
    ProjectStatus,
    Scene,
)
from app.modules.films.part_service import PartDraft, PartService
from app.modules.films.repository import FilmRepository
from app.modules.media_generation.models import (
    GenerationKind,
    GenerationRequest,
    GenerationStatus,
)

TITLE_MESSAGE = "Part title must be 1-150 characters"
PLAN_MESSAGE = "Part plan must be 1-5000 characters"
LENGTH_MESSAGE = "Part length must be between 8 and 600 seconds"
POSITION_MESSAGE = "Position must be between 0 and 2"
RUNNING_MESSAGE = "Episode 2 is running — stop it first"
ARCHIVED_MESSAGE = "Film project p1 is archived"
WRITE_METHODS = ("insert_part", "update_part", "move_part", "delete_part", "update_episode")


@dataclass(frozen=True)
class Outcome:
    actual: Any
    expected: Any


def build_project(**values) -> FilmProject:
    defaults = {"id": "p1", "name": "Test Series", "status": ProjectStatus.ACTIVE}
    return FilmProject(**{**defaults, **values})


def build_episode(**values) -> Episode:
    defaults = {
        "id": "e2",
        "project_id": "p1",
        "number": 2,
        "title": "Episode 2",
        "source": EpisodeSource.IDEA,
        "status": EpisodeStatus.PAUSED,
    }
    return Episode(**{**defaults, **values})


def build_part(part_id: str, position: int) -> EpisodePart:
    return EpisodePart(
        id=part_id,
        episode_id="e2",
        position=position,
        title=f"Part {position + 1} title",
        plan="Mai dives.",
        target_duration_s=60,
        recap=None,
    )


def build_scene(scene_id: str) -> Scene:
    return Scene(
        id=scene_id,
        episode_id="e2",
        part_id="pt2",
        position=0,
        image_prompt="Mai at the pier",
        video_prompt="0-3s: Mai walks.",
        character_ids=[],
        clip_duration_s=8,
        image_status=MediaStatus.NONE,
        clip_status=MediaStatus.NONE,
        narration_status=MediaStatus.NONE,
    )


def build_request(request_id: str, scene_id: str | None) -> GenerationRequest:
    return GenerationRequest(
        id=request_id,
        kind=GenerationKind.SCENE_CLIP if scene_id else GenerationKind.MUSIC,
        episode_id="e2",
        scene_id=scene_id,
        status=GenerationStatus.QUEUED,
        params={},
    )


def build_draft(**values) -> PartDraft:
    defaults = {
        "after_position": None,
        "title": " The Dive ",
        "plan": " Mai dives. ",
        "target_duration_s": 60,
    }
    return PartDraft(**{**defaults, **values})


EPISODE_PARTS = [build_part("pt1", 0), build_part("pt2", 1), build_part("pt3", 2)]
PART = EPISODE_PARTS[1]


def build_tools(episode: Episode | None = None, project: FilmProject | None = None):
    repository = MagicMock(spec=FilmRepository)
    repository.find_project.return_value = project or build_project()
    repository.find_episode.return_value = episode or build_episode()
    repository.find_parts.return_value = EPISODE_PARTS
    repository.find_part.return_value = PART
    repository.count_scenes_by_part.return_value = {}
    return SimpleNamespace(
        service=PartService(repository, FilmAccess(repository)), repository=repository
    )


def is_written(repository) -> bool:
    return any(getattr(repository, method).called for method in WRITE_METHODS)


def inserted_part(tools) -> EpisodePart:
    return tools.repository.insert_part.call_args.args[0]


@pytest.fixture
def added_part():
    tools = build_tools()
    result = tools.service.add_part("e2", build_draft())
    return SimpleNamespace(result=result, inserted=inserted_part(tools), tools=tools)


def test_an_added_part_is_saved_trimmed_without_a_recap(added_part):
    inserted = added_part.inserted
    assert (
        inserted.episode_id,
        inserted.title,
        inserted.plan,
        inserted.target_duration_s,
        inserted.recap,
    ) == ("e2", "The Dive", "Mai dives.", 60, None)


def test_an_added_part_is_answered_as_saved(added_part):
    assert (added_part.result, added_part.tools.repository.find_part.call_args.args) == (
        PART,
        (added_part.inserted.id,),
    )


def test_an_added_part_counts_the_parts_of_its_episode(added_part):
    assert added_part.tools.repository.find_parts.call_args_list == [call("e2")]


@pytest.fixture(params=[(None, 3), (-1, 0), (0, 1), (1, 2), (2, 3), (9, 3)])
def added_part_position(request):
    after_position, expected = request.param
    tools = build_tools()
    tools.service.add_part("e2", build_draft(after_position=after_position))
    return Outcome(inserted_part(tools).position, expected)


def test_an_added_part_goes_after_the_given_position_or_at_the_end(added_part_position):
    assert added_part_position.actual == added_part_position.expected


@pytest.fixture(
    params=[
        (
            {"title": "x" * 150, "plan": "y" * 5000, "target_duration_s": 8},
            ("x" * 150, "y" * 5000, 8),
        ),
        ({"target_duration_s": 600}, ("The Dive", "Mai dives.", 600)),
    ]
)
def accepted_part_limits(request):
    draft_values, expected = request.param
    tools = build_tools()
    tools.service.add_part("e2", build_draft(**draft_values))
    inserted = inserted_part(tools)
    return Outcome((inserted.title, inserted.plan, inserted.target_duration_s), expected)


def test_a_part_at_the_limits_is_added(accepted_part_limits):
    assert accepted_part_limits.actual == accepted_part_limits.expected


@pytest.fixture(
    params=[
        ({"title": "   "}, TITLE_MESSAGE),
        ({"title": "x" * 151}, TITLE_MESSAGE),
        ({"plan": ""}, PLAN_MESSAGE),
        ({"plan": "y" * 5001}, PLAN_MESSAGE),
        ({"target_duration_s": 7}, LENGTH_MESSAGE),
        ({"target_duration_s": 601}, LENGTH_MESSAGE),
    ]
)
def rejected_added_part(request):
    draft_values, message = request.param
    tools = build_tools()
    with pytest.raises(InvalidFilmRequestError) as error:
        tools.service.add_part("e2", build_draft(**draft_values))
    return Outcome((str(error.value), is_written(tools.repository)), (message, False))


def test_an_invalid_part_is_refused_and_adds_nothing(rejected_added_part):
    assert rejected_added_part.actual == rejected_added_part.expected


@pytest.fixture(
    params=[
        EpisodeStatus.DRAFT,
        EpisodeStatus.PAUSED,
        EpisodeStatus.FAILED,
        EpisodeStatus.DONE,
    ]
)
def added_part_in_status(request):
    tools = build_tools(build_episode(status=request.param))
    tools.service.add_part("e2", build_draft())
    return tools.repository.insert_part.called


def test_a_part_is_added_in_every_status_but_running(added_part_in_status):
    assert added_part_in_status is True


PART_ACTIONS = {
    "add": lambda service: service.add_part("e2", build_draft()),
    "update": lambda service: service.update_part("pt2", {"title": "The Deep"}),
    "move": lambda service: service.update_part("pt2", {"position": 0}),
    "delete": lambda service: service.delete_part("pt2"),
}


@pytest.fixture(
    params=[
        ("add", EpisodeStatus.RUNNING, ProjectStatus.ACTIVE, EpisodeRunningError, RUNNING_MESSAGE),
        (
            "update",
            EpisodeStatus.RUNNING,
            ProjectStatus.ACTIVE,
            EpisodeRunningError,
            RUNNING_MESSAGE,
        ),
        ("move", EpisodeStatus.RUNNING, ProjectStatus.ACTIVE, EpisodeRunningError, RUNNING_MESSAGE),
        (
            "delete",
            EpisodeStatus.RUNNING,
            ProjectStatus.ACTIVE,
            EpisodeRunningError,
            RUNNING_MESSAGE,
        ),
        ("add", EpisodeStatus.DONE, ProjectStatus.ARCHIVED, FilmConflictError, ARCHIVED_MESSAGE),
        ("update", EpisodeStatus.DONE, ProjectStatus.ARCHIVED, FilmConflictError, ARCHIVED_MESSAGE),
        ("delete", EpisodeStatus.DONE, ProjectStatus.ARCHIVED, FilmConflictError, ARCHIVED_MESSAGE),
    ]
)
def refused_part_action(request):
    action, episode_status, project_status, error_class, message = request.param
    tools = build_tools(build_episode(status=episode_status), build_project(status=project_status))
    with pytest.raises(error_class) as error:
        PART_ACTIONS[action](tools.service)
    return Outcome((str(error.value), is_written(tools.repository)), (message, False))


def test_parts_are_not_changed_while_running_or_archived(refused_part_action):
    assert refused_part_action.actual == refused_part_action.expected


@pytest.fixture(
    params=[
        (lambda service: service.add_part("e9", build_draft()), "Episode e9 not found"),
        (lambda service: service.get_part_detail("pt9"), "Part pt9 not found"),
        (lambda service: service.update_part("pt9", {"title": "The Deep"}), "Part pt9 not found"),
        (lambda service: service.delete_part("pt9"), "Part pt9 not found"),
    ]
)
def unknown_part_error(request):
    run_action, message = request.param
    tools = build_tools()
    tools.repository.find_episode.return_value = None
    tools.repository.find_part.return_value = None
    with pytest.raises(FilmNotFoundError) as error:
        run_action(tools.service)
    return Outcome((str(error.value), is_written(tools.repository)), (message, False))


def test_an_unknown_part_or_episode_answers_not_found(unknown_part_error):
    assert unknown_part_error.actual == unknown_part_error.expected


PART_SCENES = [build_scene("s1"), build_scene("s2")]
PART_REQUEST = build_request("r-clip", "s1")


@pytest.fixture
def part_detail():
    tools = build_tools(build_episode(status=EpisodeStatus.DONE))
    tools.repository.find_part_scenes.return_value = PART_SCENES
    tools.repository.find_open_requests_for_episode.return_value = [
        PART_REQUEST,
        build_request("r-other", "s9"),
        build_request("r-music", None),
    ]
    return SimpleNamespace(detail=tools.service.get_part_detail("pt2"), tools=tools)


def test_the_part_detail_holds_the_part_its_scenes_and_only_their_open_requests(part_detail):
    detail = part_detail.detail
    assert (detail.part, detail.scenes, detail.open_requests) == (
        PART,
        PART_SCENES,
        [PART_REQUEST],
    )


def test_the_part_detail_reads_the_scenes_of_the_part_and_the_requests_of_its_episode(
    part_detail,
):
    repository = part_detail.tools.repository
    assert (
        repository.find_part_scenes.call_args_list,
        repository.find_open_requests_for_episode.call_args_list,
    ) == ([call("pt2")], [call("e2")])


@pytest.fixture
def edited_part():
    tools = build_tools()
    result = tools.service.update_part(
        "pt2", {"title": " The Deep ", "plan": " Mai sinks. ", "target_duration_s": 90}
    )
    return SimpleNamespace(result=result, repository=tools.repository)


def test_a_part_edit_saves_the_trimmed_values(edited_part):
    assert edited_part.repository.update_part.call_args_list == [
        call("pt2", {"title": "The Deep", "plan": "Mai sinks.", "target_duration_s": 90})
    ]


def test_a_part_edit_without_a_position_moves_nothing(edited_part):
    assert (
        edited_part.repository.move_part.called,
        edited_part.repository.update_episode.called,
    ) == (
        False,
        False,
    )


def test_a_part_edit_answers_the_saved_part(edited_part):
    assert edited_part.result is PART


@pytest.fixture(
    params=[
        ({"title": ""}, TITLE_MESSAGE),
        ({"plan": "y" * 5001}, PLAN_MESSAGE),
        ({"target_duration_s": None}, LENGTH_MESSAGE),
        ({"target_duration_s": 601}, LENGTH_MESSAGE),
        ({"position": -1}, POSITION_MESSAGE),
        ({"position": 3}, POSITION_MESSAGE),
        ({"title": "The Deep", "position": 3}, POSITION_MESSAGE),
    ]
)
def rejected_part_edit(request):
    changes, message = request.param
    tools = build_tools()
    with pytest.raises(InvalidFilmRequestError) as error:
        tools.service.update_part("pt2", changes)
    return Outcome((str(error.value), is_written(tools.repository)), (message, False))


def test_an_invalid_part_edit_is_refused_and_writes_nothing(rejected_part_edit):
    assert rejected_part_edit.actual == rejected_part_edit.expected


@pytest.fixture(
    params=[
        (EpisodeStatus.PAUSED, 0, [call(PART, 0)], []),
        (EpisodeStatus.DONE, 2, [call(PART, 2)], [call("e2", {"needs_assembly": True})]),
        (EpisodeStatus.DONE, 1, [], []),
    ]
)
def moved_part(request):
    status, position, expected_moves, expected_episode_updates = request.param
    tools = build_tools(build_episode(status=status))
    tools.service.update_part("pt2", {"position": position})
    repository = tools.repository
    return Outcome(
        actual=(
            repository.move_part.call_args_list,
            repository.update_episode.call_args_list,
            repository.update_part.called,
        ),
        expected=(expected_moves, expected_episode_updates, False),
    )


def test_a_moved_part_takes_its_new_position_and_flags_a_done_episode(moved_part):
    assert moved_part.actual == moved_part.expected


@pytest.fixture
def vanished_part_error():
    tools = build_tools()
    tools.repository.find_part.side_effect = [PART, None]
    with pytest.raises(FilmNotFoundError) as error:
        tools.service.update_part("pt2", {"title": "The Deep"})
    return error.value


def test_a_part_deleted_during_an_edit_answers_not_found(vanished_part_error):
    assert str(vanished_part_error) == "Part pt2 not found"


@pytest.fixture
def busy_part_delete():
    tools = build_tools()
    tools.repository.count_scenes_by_part.return_value = {"pt2": 3}
    with pytest.raises(FilmConflictError) as error:
        tools.service.delete_part("pt2")
    return SimpleNamespace(error=error.value, repository=tools.repository)


def test_a_part_with_scenes_is_not_deleted(busy_part_delete):
    assert (str(busy_part_delete.error), busy_part_delete.repository.delete_part.called) == (
        "Part 2 has scenes — delete them first",
        False,
    )


def test_the_scenes_of_the_part_are_counted(busy_part_delete):
    assert busy_part_delete.repository.count_scenes_by_part.call_args_list == [call(["pt2"])]


@pytest.fixture
def deleted_part():
    tools = build_tools(build_episode(status=EpisodeStatus.DONE))
    tools.service.delete_part("pt2")
    return tools.repository


def test_a_part_without_scenes_is_deleted(deleted_part):
    assert deleted_part.delete_part.call_args_list == [call(PART)]
