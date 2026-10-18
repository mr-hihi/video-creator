import io
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, call

import pytest

from app.modules.films.errors import (
    EpisodeRunningError,
    FilmConflictError,
    FilmFileTooLargeError,
    FilmNotFoundError,
    InvalidFilmRequestError,
)
from app.modules.films.film_access import FilmAccess
from app.modules.films.film_files import BYTES_PER_MB, FilmFiles
from app.modules.films.media_queue import FilmMediaQueue, SceneOrderContext
from app.modules.films.models import (
    Character,
    EntityType,
    Episode,
    EpisodeStatus,
    FilmProject,
    MediaStatus,
    ProjectStatus,
    Scene,
    SceneImageSource,
    VoiceTemplate,
)
from app.modules.films.repository import FilmRepository
from app.modules.films.scene_service import SceneDraft, SceneService, SceneServiceTools
from app.modules.films.upload_rules import FileUpload

UPLOAD_MAX_MB = 1
MAI = Character(id="c1", name="Mai", entity_type=EntityType.CHARACTER)
HARBOR = Character(id="c2", name="Old Harbor", entity_type=EntityType.LOCATION)
VOICE = VoiceTemplate(id="v1", name="narrator-en")
NARRATION_RESET_VALUES = {
    "narration_status": MediaStatus.NONE,
    "narration_path": None,
    "narration_duration_ms": None,
}


@dataclass(frozen=True)
class Outcome:
    actual: Any
    expected: Any


def build_project(**values) -> FilmProject:
    defaults = {
        "id": "p1",
        "status": ProjectStatus.ACTIVE,
        "narrator_voice_id": "v1",
        "allow_narration": True,
        "clip_duration_s": 8,
    }
    return FilmProject(**{**defaults, **values})


def build_episode(**values) -> Episode:
    defaults = {"id": "e1", "project_id": "p1", "number": 1, "status": EpisodeStatus.PAUSED}
    return Episode(**{**defaults, **values})


def build_scene(**values) -> Scene:
    defaults = {
        "id": "s1",
        "episode_id": "e1",
        "position": 0,
        "image_prompt": "Mai stands on the pier",
        "video_prompt": "0-3s: Mai walks.",
        "narrator_text": "The fog never lifts here.",
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


def build_draft(**values) -> SceneDraft:
    defaults = {
        "after_position": None,
        "image_prompt": " Close-up of the bell ",
        "video_prompt": "0-3s: The bell sways.",
        "narrator_text": "  ",
        "character_ids": ["c1", "c1", "c2"],
    }
    return SceneDraft(**{**defaults, **values})


def build_parts(tmp_path, scene: Scene | None = None, **records):
    scene = scene or build_scene()
    episode = records.get("episode") or build_episode()
    project = records.get("project") or build_project()
    repository = MagicMock(spec=FilmRepository)
    repository.find_scene.return_value = scene
    repository.find_episode.return_value = episode
    repository.find_project.return_value = project
    repository.find_open_requests_for_scene.return_value = []
    repository.count_scenes_by_episode.return_value = {"e1": 3}
    repository.find_project_characters.return_value = [MAI, HARBOR]
    repository.find_characters_by_ids.return_value = {"c1": MAI, "c2": HARBOR}
    repository.find_voice.return_value = VOICE
    media_queue = MagicMock(spec=FilmMediaQueue)
    files = FilmFiles(tmp_path, UPLOAD_MAX_MB)
    service = SceneService(
        SceneServiceTools(
            repository=repository,
            access=FilmAccess(repository),
            files=files,
            media_queue=media_queue,
        )
    )
    return SimpleNamespace(
        service=service,
        repository=repository,
        media_queue=media_queue,
        files=files,
        scene=scene,
        episode=episode,
        project=project,
    )


def write_file(path, content: bytes = b"data"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def order_context(parts) -> SceneOrderContext:
    return SceneOrderContext(parts.project, "e1", parts.scene)


def is_assembly_flagged(parts) -> bool:
    return any(
        call.args == ("e1", {"needs_assembly": True})
        for call in parts.repository.update_episode.call_args_list
    )


@pytest.fixture(params=[(None, 3), (-1, 0), (0, 1), (99, 3), (-5, 0)])
def inserted_position(request, tmp_path):
    after_position, expected_position = request.param
    parts = build_parts(tmp_path)
    parts.service.add_scene("e1", build_draft(after_position=after_position))
    return Outcome(parts.repository.insert_scene.call_args.args[0].position, expected_position)


def test_a_new_scene_goes_after_the_given_position(inserted_position):
    assert inserted_position.actual == inserted_position.expected


@pytest.fixture
def added_scene(tmp_path):
    parts = build_parts(tmp_path)
    returned = parts.service.add_scene("e1", build_draft())
    return SimpleNamespace(
        scene=parts.repository.insert_scene.call_args.args[0], returned=returned, parts=parts
    )


def test_a_new_scene_starts_empty_with_the_default_trim(added_scene):
    scene = added_scene.scene
    assert (
        scene.episode_id,
        scene.image_prompt,
        scene.video_prompt,
        scene.narrator_text,
        scene.character_ids,
        scene.clip_duration_s,
        scene.image_status,
        scene.clip_status,
        scene.narration_status,
        scene.trim_start_ms,
        scene.trim_end_ms,
    ) == (
        "e1",
        "Close-up of the bell",
        "0-3s: The bell sways.",
        None,
        ["c1", "c2"],
        8,
        MediaStatus.NONE,
        MediaStatus.NONE,
        MediaStatus.NONE,
        1000,
        None,
    )


@pytest.fixture
def long_scene(tmp_path):
    parts = build_parts(tmp_path)
    parts.service.add_scene("e1", build_draft(clip_duration_s=25))
    return parts.repository.insert_scene.call_args.args[0]


def test_a_new_scene_keeps_the_clip_length_it_was_given(long_scene):
    assert long_scene.clip_duration_s == 25


def test_adding_a_scene_answers_the_saved_scene(added_scene):
    assert added_scene.returned is added_scene.parts.scene


def test_adding_to_a_paused_episode_keeps_the_assembly_flag(added_scene):
    assert not added_scene.parts.repository.update_episode.called


@pytest.fixture
def scene_added_to_done_episode(tmp_path):
    parts = build_parts(tmp_path, episode=build_episode(status=EpisodeStatus.DONE))
    parts.service.add_scene("e1", build_draft(character_ids=[]))
    return parts


def test_adding_to_a_done_episode_needs_assembly(scene_added_to_done_episode):
    scene_added_to_done_episode.repository.update_episode.assert_called_once_with(
        "e1", {"needs_assembly": True}
    )


def test_a_scene_without_characters_reads_no_cast(scene_added_to_done_episode):
    assert not scene_added_to_done_episode.repository.find_project_characters.called


@pytest.fixture(
    params=[
        ({}, {"count": 80}, InvalidFilmRequestError, "An episode holds at most 80 scenes"),
        ({"clip_duration_s": 3}, {}, InvalidFilmRequestError, "Clip length must be 4-30 seconds"),
        ({"clip_duration_s": 31}, {}, InvalidFilmRequestError, "Clip length must be 4-30 seconds"),
        (
            {"image_prompt": ""},
            {},
            InvalidFilmRequestError,
            "Image prompt must be 1-4000 characters",
        ),
        (
            {"video_prompt": "v" * 4001},
            {},
            InvalidFilmRequestError,
            "Video prompt must be 1-4000 characters",
        ),
        (
            {"narrator_text": "a" * 1001},
            {},
            InvalidFilmRequestError,
            "Narration must be at most 1000 characters",
        ),
        (
            {"character_ids": ["c1", "c3"]},
            {},
            InvalidFilmRequestError,
            "Character c3 is not in this project",
        ),
        (
            {},
            {"episode": build_episode(status=EpisodeStatus.RUNNING)},
            EpisodeRunningError,
            "Episode 1 is running — stop it first",
        ),
        (
            {},
            {"project": build_project(status=ProjectStatus.ARCHIVED)},
            FilmConflictError,
            "Film project p1 is archived",
        ),
        ({}, {"episode_missing": True}, FilmNotFoundError, "Episode e1 not found"),
    ]
)
def rejected_add(request, tmp_path):
    draft_values, setup, error_class, message = request.param
    parts = build_parts(tmp_path, episode=setup.get("episode"), project=setup.get("project"))
    parts.repository.count_scenes_by_episode.return_value = {"e1": setup.get("count", 3)}
    if setup.get("episode_missing"):
        parts.repository.find_episode.return_value = None
    with pytest.raises(error_class) as error:
        parts.service.add_scene("e1", build_draft(**draft_values))
    return Outcome(
        actual=(str(error.value), parts.repository.insert_scene.called),
        expected=(message, False),
    )


def test_an_invalid_scene_is_not_added(rejected_add):
    assert rejected_add.actual == rejected_add.expected


CLIP_SCENE = {
    "position": 1,
    "clip_status": MediaStatus.DONE,
    "clip_duration_ms": 8000,
    "trim_start_ms": 1000,
}


@pytest.fixture(
    params=[
        (
            {},
            {"image_prompt": " "},
            InvalidFilmRequestError,
            "Image prompt must be 1-4000 characters",
        ),
        (
            {},
            {"video_prompt": None},
            InvalidFilmRequestError,
            "Video prompt must be 1-4000 characters",
        ),
        (
            {},
            {"narrator_text": "a" * 1001},
            InvalidFilmRequestError,
            "Narration must be at most 1000 characters",
        ),
        (
            {},
            {"character_ids": ["c3"]},
            InvalidFilmRequestError,
            "Character c3 is not in this project",
        ),
        ({}, {"clip_duration_s": 31}, InvalidFilmRequestError, "Clip length must be 4-30 seconds"),
        (
            {},
            {"clip_duration_s": None},
            InvalidFilmRequestError,
            "Clip length must be 4-30 seconds",
        ),
        ({}, {"position": 99}, InvalidFilmRequestError, "Position must be between 0 and 2"),
        ({}, {"position": -1}, InvalidFilmRequestError, "Position must be between 0 and 2"),
        (
            {"position": 1},
            {"trim_start_ms": 1000, "trim_end_ms": 5000},
            FilmConflictError,
            "Scene 2 has no clip yet",
        ),
        (
            CLIP_SCENE,
            {"trim_start_ms": 7500, "trim_end_ms": 8000},
            InvalidFilmRequestError,
            "Trim must keep at least 1 s inside the clip",
        ),
        (
            CLIP_SCENE,
            {"trim_start_ms": 0, "trim_end_ms": 9000},
            InvalidFilmRequestError,
            "Trim must keep at least 1 s inside the clip",
        ),
        (
            CLIP_SCENE,
            {"trim_start_ms": 3000, "trim_end_ms": 2000},
            InvalidFilmRequestError,
            "Trim must keep at least 1 s inside the clip",
        ),
        (
            CLIP_SCENE,
            {"trim_start_ms": -1},
            InvalidFilmRequestError,
            "Trim must keep at least 1 s inside the clip",
        ),
    ]
)
def rejected_update(request, tmp_path):
    scene_values, changes, error_class, message = request.param
    parts = build_parts(tmp_path, build_scene(**scene_values))
    with pytest.raises(error_class) as error:
        parts.service.update_scene("s1", changes)
    return Outcome(
        actual=(
            str(error.value),
            parts.repository.update_scene.called,
            parts.repository.move_scene.called,
        ),
        expected=(message, False, False),
    )


def test_an_invalid_edit_changes_nothing(rejected_update):
    assert rejected_update.actual == rejected_update.expected


@pytest.fixture(params=["running", "missing"])
def refused_scene_edit(request, tmp_path):
    parts = build_parts(tmp_path, episode=build_episode(status=EpisodeStatus.RUNNING))
    if request.param == "missing":
        parts.repository.find_scene.return_value = None
    with pytest.raises((EpisodeRunningError, FilmNotFoundError)) as error:
        parts.service.update_scene("s9", {"image_prompt": "Wider shot"})
    expected = {
        "running": "Episode 1 is running — stop it first",
        "missing": "Scene s9 not found",
    }[request.param]
    return Outcome(str(error.value), expected)


def test_a_scene_of_a_running_episode_or_an_unknown_scene_is_refused(refused_scene_edit):
    assert refused_scene_edit.actual == refused_scene_edit.expected


@pytest.fixture(
    params=[
        ({}, {"image_prompt": " Wider shot "}, {"image_prompt": "Wider shot"}),
        (
            {},
            {"narrator_text": " A new line "},
            {"narrator_text": "A new line", **NARRATION_RESET_VALUES},
        ),
        ({}, {"narrator_text": None}, {"narrator_text": None, **NARRATION_RESET_VALUES}),
        ({}, {"character_ids": None}, {"character_ids": []}),
        (CLIP_SCENE, {"clip_duration_s": 20}, {"clip_duration_s": 20}),
        ({}, {"character_ids": ["c2", "c2"]}, {"character_ids": ["c2"]}),
        (
            CLIP_SCENE,
            {"trim_start_ms": 1500, "trim_end_ms": 6500},
            {"trim_start_ms": 1500, "trim_end_ms": 6500},
        ),
        (
            {**CLIP_SCENE, "trim_start_ms": 1500, "trim_end_ms": 6500},
            {"trim_end_ms": None},
            {"trim_start_ms": 1500, "trim_end_ms": None},
        ),
        (
            {**CLIP_SCENE, "trim_start_ms": 1500},
            {"trim_start_ms": None},
            {"trim_start_ms": 1000, "trim_end_ms": None},
        ),
    ]
)
def accepted_update(request, tmp_path):
    scene_values, changes, expected_values = request.param
    parts = build_parts(tmp_path, build_scene(**scene_values))
    parts.service.update_scene("s1", changes)
    return Outcome(parts.repository.update_scene.call_args.args, ("s1", expected_values))


def test_an_allowed_edit_writes_the_normalised_values(accepted_update):
    assert accepted_update.actual == accepted_update.expected


@pytest.fixture(params=[{"narrator_text": "The fog never lifts here."}, {"position": None}])
def edit_without_change(request, tmp_path):
    parts = build_parts(tmp_path)
    parts.service.update_scene("s1", request.param)
    return parts


def test_an_edit_that_changes_nothing_writes_nothing(edit_without_change):
    assert (
        edit_without_change.repository.update_scene.called,
        edit_without_change.repository.move_scene.called,
    ) == (False, False)


@pytest.fixture(params=[(2, True), (0, False)])
def moved_scene(request, tmp_path):
    position, is_moved = request.param
    parts = build_parts(tmp_path)
    parts.service.update_scene("s1", {"position": position})
    return Outcome(
        actual=parts.repository.move_scene.call_args_list,
        expected=[call(parts.scene, position)] if is_moved else [],
    )


def test_only_a_new_position_moves_the_scene(moved_scene):
    assert moved_scene.actual == moved_scene.expected


@pytest.fixture
def vanished_scene_error(tmp_path):
    parts = build_parts(tmp_path)
    parts.repository.find_scene.side_effect = [parts.scene, None]
    with pytest.raises(FilmNotFoundError) as error:
        parts.service.update_scene("s1", {"image_prompt": "Wider shot"})
    return error.value


def test_a_scene_deleted_during_the_edit_is_not_found(vanished_scene_error):
    assert str(vanished_scene_error) == "Scene s1 not found"


@pytest.fixture
def narration_edit(tmp_path):
    scene = build_scene(
        narration_status=MediaStatus.DONE,
        narration_path="projects/p1/episodes/e1/scenes/s1/narration.mp3",
    )
    parts = build_parts(tmp_path, scene)
    narration_file = write_file(parts.files.to_absolute(scene.narration_path))
    returned = parts.service.update_scene("s1", {"narrator_text": "A new line"})
    return SimpleNamespace(parts=parts, narration_file=narration_file, returned=returned)


def test_a_new_narration_text_deletes_the_old_narration(narration_edit):
    assert not narration_edit.narration_file.exists()


def test_a_scene_edit_answers_the_saved_scene(narration_edit):
    assert narration_edit.returned is narration_edit.parts.scene


@pytest.fixture(
    params=[
        (CLIP_SCENE, {"trim_start_ms": 1500}, True),
        (CLIP_SCENE, {"trim_start_ms": 1000}, False),
        ({}, {"narrator_text": "A new line"}, True),
        ({}, {"position": 2}, True),
        ({}, {"image_prompt": "Wider shot"}, False),
    ]
)
def done_episode_edit(request, tmp_path):
    scene_values, changes, expected_flag = request.param
    parts = build_parts(
        tmp_path, build_scene(**scene_values), episode=build_episode(status=EpisodeStatus.DONE)
    )
    parts.service.update_scene("s1", changes)
    return Outcome(is_assembly_flagged(parts), expected_flag)


def test_a_reset_trim_or_move_on_a_done_episode_needs_assembly(done_episode_edit):
    assert done_episode_edit.actual == done_episode_edit.expected


@pytest.fixture
def busy_scene_parts(tmp_path):
    parts = build_parts(tmp_path, build_scene(image_status=MediaStatus.DONE))
    parts.repository.find_open_requests_for_scene.return_value = ["request-1"]
    return parts


@pytest.fixture(
    params=["delete", "upload", "generate_image", "edit_image", "generate_clip", "narration"]
)
def busy_scene_error(request, busy_scene_parts):
    service = busy_scene_parts.service
    actions = {
        "delete": lambda: service.delete_scene("s1"),
        "upload": lambda: service.upload_image("s1", FileUpload("a.png", io.BytesIO(b"x"))),
        "generate_image": lambda: service.generate_image("s1"),
        "edit_image": lambda: service.edit_image("s1", "Make it night"),
        "generate_clip": lambda: service.generate_clip("s1"),
        "narration": lambda: service.generate_narration("s1"),
    }
    with pytest.raises(FilmConflictError) as error:
        actions[request.param]()
    return error.value


def test_a_scene_with_generation_running_refuses_files_and_generation(busy_scene_error):
    assert str(busy_scene_error) == "Scene 1 has generation running"


def test_a_refused_action_queues_and_deletes_nothing(busy_scene_parts, busy_scene_error):
    assert (
        busy_scene_parts.repository.delete_scene.called,
        busy_scene_parts.repository.update_scene.called,
        busy_scene_parts.media_queue.method_calls,
    ) == (False, False, [])


@pytest.fixture
def deleted_scene(tmp_path):
    parts = build_parts(tmp_path, episode=build_episode(status=EpisodeStatus.DONE))
    scene_dir = parts.files.scene_dir("p1", "e1", "s1")
    write_file(scene_dir / "image.png")
    parts.service.delete_scene("s1")
    return SimpleNamespace(parts=parts, scene_dir=scene_dir)


def test_deleting_a_scene_closes_the_gap_in_the_repository(deleted_scene):
    deleted_scene.parts.repository.delete_scene.assert_called_once_with(deleted_scene.parts.scene)


def test_deleting_a_scene_removes_its_folder(deleted_scene):
    assert not deleted_scene.scene_dir.exists()


def test_deleting_a_scene_of_a_done_episode_needs_assembly(deleted_scene):
    deleted_scene.parts.repository.update_episode.assert_called_once_with(
        "e1", {"needs_assembly": True}
    )


@pytest.fixture
def uploaded_image(tmp_path):
    scene = build_scene(
        image_status=MediaStatus.DONE,
        clip_status=MediaStatus.DONE,
        clip_path="projects/p1/episodes/e1/scenes/s1/clip.mp4",
        trim_start_ms=1500,
        trim_end_ms=6500,
    )
    parts = build_parts(tmp_path, scene, episode=build_episode(status=EpisodeStatus.DONE))
    clip_file = write_file(parts.files.to_absolute(scene.clip_path))
    segment_file = write_file(parts.files.scene_clip_segments_dir("p1", "e1", "s1") / "1.mp4")
    old_image = write_file(parts.files.scene_image_path("p1", "e1", "s1", "png"))
    returned = parts.service.upload_image("s1", FileUpload("IMG-L.JPG", io.BytesIO(b"new image")))
    return SimpleNamespace(
        parts=parts,
        returned=returned,
        clip_file=clip_file,
        segment_file=segment_file,
        old_image=old_image,
        new_image=parts.files.scene_image_path("p1", "e1", "s1", "jpg"),
    )


def test_an_uploaded_image_is_done_and_resets_the_clip(uploaded_image):
    uploaded_image.parts.repository.update_scene.assert_called_once_with(
        "s1",
        {
            "clip_status": MediaStatus.NONE,
            "clip_path": None,
            "clip_duration_ms": None,
            "trim_start_ms": 1000,
            "trim_end_ms": None,
            "image_status": MediaStatus.DONE,
            "image_source": SceneImageSource.UPLOADED,
            "image_error": None,
            "provider_media": None,
            "image_path": "projects/p1/episodes/e1/scenes/s1/image.jpg",
        },
    )


def test_the_upload_replaces_the_image_file(uploaded_image):
    assert (uploaded_image.new_image.read_bytes(), uploaded_image.old_image.exists()) == (
        b"new image",
        False,
    )


def test_the_upload_deletes_the_old_clip(uploaded_image):
    assert not uploaded_image.clip_file.exists()


def test_the_upload_deletes_the_segments_of_the_old_image(uploaded_image):
    assert not uploaded_image.segment_file.parent.exists()


def test_an_upload_on_a_done_episode_needs_assembly(uploaded_image):
    uploaded_image.parts.repository.update_episode.assert_called_once_with(
        "e1", {"needs_assembly": True}
    )


def test_the_upload_answers_the_saved_scene(uploaded_image):
    assert uploaded_image.returned is uploaded_image.parts.scene


@pytest.fixture(
    params=[
        (
            FileUpload("IMG.gif", io.BytesIO(b"gif")),
            InvalidFilmRequestError,
            "Unsupported image type '.gif'. Use one of: .jpeg, .jpg, .png, .webp",
        ),
        (
            FileUpload("big.png", io.BytesIO(b"x" * (BYTES_PER_MB + 1))),
            FilmFileTooLargeError,
            "Image exceeds 1 MB",
        ),
    ]
)
def rejected_upload(request, tmp_path):
    upload, error_class, message = request.param
    parts = build_parts(tmp_path)
    with pytest.raises(error_class) as error:
        parts.service.upload_image("s1", upload)
    return Outcome((str(error.value), parts.repository.update_scene.called), (message, False))


def test_an_unsupported_or_too_large_image_is_refused(rejected_upload):
    assert rejected_upload.actual == rejected_upload.expected


@pytest.fixture(
    params=[
        (
            {"c1": MediaStatus.NONE, "c2": MediaStatus.DONE},
            "Generate the reference images of Mai first",
        ),
        (
            {"c1": MediaStatus.FAILED, "c2": MediaStatus.QUEUED},
            "Generate the reference images of Mai, Old Harbor first",
        ),
    ]
)
def missing_reference_error(request, tmp_path):
    statuses, message = request.param
    parts = build_parts(tmp_path, build_scene(character_ids=["c1", "c2", "c9"]))
    parts.repository.find_characters_by_ids.return_value = {
        character_id: Character(id=character_id, name=name, reference_status=statuses[character_id])
        for character_id, name in (("c1", "Mai"), ("c2", "Old Harbor"))
    }
    with pytest.raises(FilmConflictError) as error:
        parts.service.generate_image("s1")
    return Outcome((str(error.value), parts.media_queue.method_calls), (message, []))


def test_a_scene_image_needs_the_references_of_its_characters(missing_reference_error):
    assert missing_reference_error.actual == missing_reference_error.expected


@pytest.fixture(
    params=[
        ("generate_clip", {}, "Scene 1 has no image yet"),
        ("generate_narration", {"narrator_text": None}, "Scene 1 has no narration text"),
        ("generate_narration", {"narrator_text": "   "}, "Scene 1 has no narration text"),
        ("edit_image", {}, "Scene 1 has no image to edit"),
    ]
)
def missing_input_error(request, tmp_path):
    action, scene_values, message = request.param
    parts = build_parts(tmp_path, build_scene(**scene_values))
    arguments = ("s1", "Make it night") if action == "edit_image" else ("s1",)
    with pytest.raises(FilmConflictError) as error:
        getattr(parts.service, action)(*arguments)
    return Outcome((str(error.value), parts.media_queue.method_calls), (message, []))


def test_a_generation_needs_its_input(missing_input_error):
    assert missing_input_error.actual == missing_input_error.expected


@pytest.fixture(params=["no-voice-id", "voice-gone"])
def missing_narrator_error(request, tmp_path):
    project = build_project(narrator_voice_id=None if request.param == "no-voice-id" else "v1")
    parts = build_parts(tmp_path, project=project)
    parts.repository.find_voice.return_value = None
    with pytest.raises(FilmConflictError) as error:
        parts.service.generate_narration("s1")
    return error.value


def test_narration_needs_a_narrator_voice(missing_narrator_error):
    assert str(missing_narrator_error) == (
        "Pick a narrator voice for the project or turn narration off"
    )


@pytest.fixture(params=[" ", "x" * 2001])
def invalid_edit_prompt_error(request, tmp_path):
    parts = build_parts(tmp_path, build_scene(image_status=MediaStatus.DONE))
    with pytest.raises(InvalidFilmRequestError) as error:
        parts.service.edit_image("s1", request.param)
    return error.value


def test_an_edit_prompt_must_be_1_to_2000_characters(invalid_edit_prompt_error):
    assert str(invalid_edit_prompt_error) == "Edit prompt must be 1-2000 characters"


@pytest.fixture
def generation_parts(tmp_path):
    parts = build_parts(
        tmp_path,
        build_scene(image_status=MediaStatus.DONE, character_ids=["c1"]),
    )
    parts.repository.find_characters_by_ids.return_value = {
        "c1": Character(id="c1", name="Mai", reference_status=MediaStatus.DONE)
    }
    parts.media_queue.queue_scene_image.return_value = "image-request"
    parts.media_queue.queue_scene_clip.return_value = "clip-request"
    parts.media_queue.queue_narration.return_value = "narration-request"
    parts.media_queue.queue_scene_edit.return_value = "edit-request"
    return parts


@pytest.fixture
def queued_requests(generation_parts):
    service = generation_parts.service
    requests = (
        service.generate_image("s1"),
        service.generate_clip("s1"),
        service.generate_narration("s1"),
        service.edit_image("s1", " Make it night "),
    )
    return SimpleNamespace(
        requests=requests,
        context=order_context(generation_parts),
        calls=generation_parts.media_queue.method_calls,
    )


def test_each_generation_answers_its_queued_request(queued_requests):
    assert queued_requests.requests == (
        "image-request",
        "clip-request",
        "narration-request",
        "edit-request",
    )


def test_generations_are_queued_with_the_scene_and_project(queued_requests):
    assert queued_requests.calls == [
        call.queue_scene_image(queued_requests.context),
        call.queue_scene_clip(queued_requests.context),
        call.queue_narration(queued_requests.context, VOICE),
        call.queue_scene_edit(queued_requests.context, "Make it night"),
    ]
