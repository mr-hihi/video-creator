from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.films.film_files import FilmFiles
from app.modules.films.generation_targets import (
    CharacterReferenceTarget,
    EditImageTarget,
    FilmTargetTools,
    MusicTarget,
    NarrationTarget,
    SceneClipTarget,
    SceneImageTarget,
    ThumbnailTarget,
    build_film_targets,
)
from app.modules.films.models import (
    Character,
    Episode,
    EpisodeStatus,
    FilmProject,
    MediaStatus,
    ReferenceSource,
    Scene,
    SceneImageSource,
    VoiceTemplate,
)
from app.modules.films.repository import FilmRepository
from app.modules.media_generation.models import GenerationKind, GenerationRequest, GenerationStatus
from app.modules.media_generation.repository import GenerationRequestRepository

UPLOAD_MAX_MB = 20
CLIP_DURATION_MS = 8000


def build_tools(tmp_path):
    repository = MagicMock(spec=FilmRepository)
    repository.find_episode.return_value = Episode(id="e1", status=EpisodeStatus.PAUSED)
    request_repository = MagicMock(spec=GenerationRequestRepository)
    request_repository.find_by_id.return_value = None
    duration_probe = MagicMock()
    duration_probe.probe_duration_ms.return_value = CLIP_DURATION_MS
    on_final = MagicMock()
    tools = FilmTargetTools(
        repository=repository,
        files=FilmFiles(tmp_path, UPLOAD_MAX_MB),
        request_repository=request_repository,
        duration_probe=duration_probe,
        on_final=on_final,
    )
    return tools


def build_request(kind: GenerationKind, **values) -> GenerationRequest:
    defaults = {
        "id": "r1",
        "kind": kind,
        "project_id": "p1",
        "episode_id": "e1",
        "scene_id": None,
        "character_id": None,
        "provider": "google_flow",
        "params": {},
        "status": GenerationStatus.PROCESSING,
    }
    return GenerationRequest(**{**defaults, **values})


def write_file(path, content: bytes = b"data"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def updated_values(mock_method) -> dict:
    return mock_method.call_args.args[1]


@pytest.fixture
def tools(tmp_path):
    return build_tools(tmp_path)


@pytest.fixture
def character_request():
    return build_request(GenerationKind.CHARACTER_IMAGE, character_id="c1", episode_id=None)


@pytest.fixture
def queued_character(tools, character_request):
    CharacterReferenceTarget(tools).mark_queued(character_request)
    return tools.repository.update_character


@pytest.fixture
def processing_character(tools, character_request):
    CharacterReferenceTarget(tools).mark_processing(character_request)
    return tools.repository.update_character


@pytest.fixture
def saved_generated_reference(tools, character_request, tmp_path):
    target = CharacterReferenceTarget(tools)
    old_file = write_file(tools.files.character_reference_path("c1", "jpg"))
    new_file = write_file(target.output_path(character_request, "png"))
    target.save_result(character_request, new_file)
    return SimpleNamespace(
        values=updated_values(tools.repository.update_character),
        old_file=old_file,
        new_file=new_file,
    )


@pytest.fixture
def saved_edited_reference(tools):
    request = build_request(GenerationKind.EDIT_IMAGE, character_id="c1", episode_id=None)
    target = CharacterReferenceTarget(tools)
    target.save_result(request, write_file(target.output_path(request, "png")))
    return updated_values(tools.repository.update_character)


@pytest.fixture(
    params=[("characters/c1/reference.png", MediaStatus.DONE), (None, MediaStatus.FAILED)]
)
def failed_character(request, tools, character_request):
    reference_path, expected = request.param
    tools.repository.find_character.return_value = Character(id="c1", reference_path=reference_path)
    CharacterReferenceTarget(tools).mark_failed(character_request, "Blocked")
    return SimpleNamespace(
        actual=updated_values(tools.repository.update_character), expected=expected
    )


@pytest.fixture(
    params=[("characters/c1/reference.png", MediaStatus.DONE), (None, MediaStatus.NONE)]
)
def cancelled_character(request, tools, character_request):
    reference_path, expected = request.param
    tools.repository.find_character.return_value = Character(id="c1", reference_path=reference_path)
    CharacterReferenceTarget(tools).mark_cancelled(character_request)
    return SimpleNamespace(
        actual=updated_values(tools.repository.update_character), expected=expected
    )


@pytest.fixture
def missing_character_updates(tools, character_request):
    tools.repository.find_character.return_value = None
    target = CharacterReferenceTarget(tools)
    target.mark_failed(character_request, "Blocked")
    target.mark_cancelled(character_request)
    return tools.repository.update_character


@pytest.fixture
def scene_image_request():
    return build_request(GenerationKind.SCENE_IMAGE, scene_id="s1")


def build_scene(**values) -> Scene:
    defaults = {
        "id": "s1",
        "episode_id": "e1",
        "position": 0,
        "character_ids": ["c1", "c2"],
        "image_status": MediaStatus.PROCESSING,
        "clip_status": MediaStatus.DONE,
        "narration_status": MediaStatus.NONE,
        "clip_path": None,
        "image_path": None,
        "narration_path": None,
    }
    return Scene(**{**defaults, **values})


@pytest.fixture
def ready_scene_image(tools, scene_image_request):
    tools.repository.find_scene.return_value = build_scene()
    tools.repository.find_characters_by_ids.return_value = {
        "c1": Character(id="c1", name="Mai", reference_status=MediaStatus.DONE),
        "c2": Character(id="c2", name="Old Harbor", reference_status=MediaStatus.DONE),
    }
    return SceneImageTarget(tools).is_ready(scene_image_request)


@pytest.fixture
def blocked_scene_image(tools, scene_image_request):
    tools.repository.find_scene.return_value = build_scene()
    tools.repository.find_characters_by_ids.return_value = {
        "c1": Character(id="c1", name="Mai", reference_status=MediaStatus.FAILED),
        "c2": Character(id="c2", name="Old Harbor", reference_status=MediaStatus.DONE),
    }
    is_ready = SceneImageTarget(tools).is_ready(scene_image_request)
    return SimpleNamespace(is_ready=is_ready, tools=tools)


@pytest.fixture
def edit_request_readiness(tools):
    request = build_request(GenerationKind.EDIT_IMAGE, scene_id="s1")
    return SceneImageTarget(tools).is_ready(request)


@pytest.fixture
def missing_scene_readiness(tools, scene_image_request):
    tools.repository.find_scene.return_value = None
    return SceneImageTarget(tools).is_ready(scene_image_request)


@pytest.fixture
def saved_scene_image(tools, scene_image_request):
    target = SceneImageTarget(tools)
    old_clip = write_file(tools.files.scene_clip_path("p1", "e1", "s1", "mp4"))
    old_segment = write_file(tools.files.scene_clip_segments_dir("p1", "e1", "s1") / "1.mp4")
    tools.repository.find_scene.return_value = build_scene(
        clip_path=tools.files.to_relative(old_clip)
    )
    tools.repository.find_episode.return_value = Episode(id="e1", status=EpisodeStatus.DONE)
    new_image = write_file(target.output_path(scene_image_request, "png"))
    target.save_result(scene_image_request, new_image)
    return SimpleNamespace(
        values=updated_values(tools.repository.update_scene),
        old_clip=old_clip,
        old_segment=old_segment,
        episode_values=updated_values(tools.repository.update_episode),
    )


@pytest.fixture
def saved_edit_with_queued_clip(tools):
    request = build_request(GenerationKind.EDIT_IMAGE, scene_id="s1")
    target = SceneImageTarget(tools)
    tools.repository.find_scene.return_value = build_scene(clip_status=MediaStatus.QUEUED)
    target.save_result(request, write_file(target.output_path(request, "png")))
    return SimpleNamespace(
        values=updated_values(tools.repository.update_scene),
        episode_updates=tools.repository.update_episode,
    )


@pytest.fixture
def save_for_missing_scene(tools, scene_image_request):
    tools.repository.find_scene.return_value = None
    target = SceneImageTarget(tools)
    target.save_result(
        scene_image_request, write_file(target.output_path(scene_image_request, "png"))
    )
    return tools.repository.update_scene


@pytest.fixture(
    params=[("episodes/e1/scenes/s1/image.png", MediaStatus.DONE), (None, MediaStatus.FAILED)]
)
def failed_scene_image(request, tools, scene_image_request):
    image_path, expected = request.param
    tools.repository.find_scene.return_value = build_scene(image_path=image_path)
    SceneImageTarget(tools).mark_failed(scene_image_request, "Blocked by the content filter")
    return SimpleNamespace(actual=updated_values(tools.repository.update_scene), expected=expected)


@pytest.fixture(
    params=[("episodes/e1/scenes/s1/image.png", MediaStatus.DONE), (None, MediaStatus.NONE)]
)
def cancelled_scene_image(request, tools, scene_image_request):
    image_path, expected = request.param
    tools.repository.find_scene.return_value = build_scene(image_path=image_path)
    SceneImageTarget(tools).mark_cancelled(scene_image_request)
    return SimpleNamespace(actual=updated_values(tools.repository.update_scene), expected=expected)


@pytest.fixture
def missing_scene_updates(tools, scene_image_request):
    tools.repository.find_scene.return_value = None
    target = SceneImageTarget(tools)
    target.mark_failed(scene_image_request, "Blocked")
    target.mark_cancelled(scene_image_request)
    return tools.repository.update_scene


@pytest.fixture
def scene_status_updates(tools, scene_image_request):
    target = SceneImageTarget(tools)
    target.mark_queued(scene_image_request)
    target.mark_processing(scene_image_request)
    return [call.args for call in tools.repository.update_scene.call_args_list]


@pytest.fixture
def clip_request():
    return build_request(GenerationKind.SCENE_CLIP, scene_id="s1")


@pytest.fixture(
    params=[
        (MediaStatus.DONE, True),
        (MediaStatus.PROCESSING, False),
        (None, True),
    ]
)
def clip_readiness(request, tools, clip_request):
    image_status, expected = request.param
    tools.repository.find_scene.return_value = (
        None if image_status is None else build_scene(image_status=image_status)
    )
    return SimpleNamespace(actual=SceneClipTarget(tools).is_ready(clip_request), expected=expected)


@pytest.fixture
def saved_clip(tools, clip_request):
    target = SceneClipTarget(tools)
    clip_file = write_file(target.output_path(clip_request, "mp4"))
    target.save_result(clip_request, clip_file)
    return SimpleNamespace(
        values=updated_values(tools.repository.update_scene), clip_file=clip_file
    )


def build_narration_request(**values) -> GenerationRequest:
    return build_request(
        GenerationKind.NARRATION,
        scene_id="s1",
        **{"provider": "elevenlabs", "params": {"providerVoiceId": "voice-x"}, **values},
    )


def save_narration(tools, request: GenerationRequest):
    target = NarrationTarget(tools)
    target.save_result(request, write_file(target.output_path(request, "mp3")))
    return tools


@pytest.fixture
def narration_with_new_voice_copy(tools):
    tools.repository.find_project.return_value = FilmProject(id="p1", narrator_voice_id="v1")
    tools.repository.find_voice.return_value = VoiceTemplate(
        id="v1", provider_voices={"google": "voices/g"}
    )
    return save_narration(tools, build_narration_request())


@pytest.fixture(
    params=[
        "no_voice_id",
        "local_provider",
        "missing_project",
        "no_narrator",
        "missing_voice",
        "copy_known",
    ]
)
def narration_without_voice_copy(request, tools):
    tools.repository.find_project.return_value = FilmProject(id="p1", narrator_voice_id="v1")
    tools.repository.find_voice.return_value = VoiceTemplate(id="v1", provider_voices={})
    narration_request = build_narration_request()
    if request.param == "no_voice_id":
        narration_request = build_narration_request(params={})
    if request.param == "local_provider":
        narration_request = build_narration_request(provider="omnivoice")
    if request.param == "missing_project":
        tools.repository.find_project.return_value = None
    if request.param == "no_narrator":
        tools.repository.find_project.return_value = FilmProject(id="p1", narrator_voice_id=None)
    if request.param == "missing_voice":
        tools.repository.find_voice.return_value = None
    if request.param == "copy_known":
        tools.repository.find_voice.return_value = VoiceTemplate(
            id="v1", provider_voices={"elevenlabs": "voice-old"}
        )
    return save_narration(tools, narration_request)


@pytest.fixture
def music_request():
    return build_request(GenerationKind.MUSIC)


@pytest.fixture
def saved_music(tools, music_request):
    target = MusicTarget(tools)
    target.mark_queued(music_request)
    target.mark_processing(music_request)
    target.save_result(music_request, write_file(target.output_path(music_request, "mp3")))
    return [call.args for call in tools.repository.update_episode.call_args_list]


@pytest.fixture(params=[("episodes/e1/music.mp3", MediaStatus.DONE), (None, MediaStatus.FAILED)])
def failed_music(request, tools, music_request):
    music_path, expected = request.param
    tools.repository.find_episode.return_value = Episode(id="e1", music_path=music_path)
    MusicTarget(tools).mark_failed(music_request, "Quota")
    return SimpleNamespace(
        actual=updated_values(tools.repository.update_episode), expected=expected
    )


@pytest.fixture(params=[("episodes/e1/music.mp3", MediaStatus.DONE), (None, MediaStatus.NONE)])
def cancelled_music(request, tools, music_request):
    music_path, expected = request.param
    tools.repository.find_episode.return_value = Episode(id="e1", music_path=music_path)
    MusicTarget(tools).mark_cancelled(music_request)
    return SimpleNamespace(
        actual=updated_values(tools.repository.update_episode), expected=expected
    )


@pytest.fixture
def missing_episode_music_updates(tools, music_request):
    tools.repository.find_episode.return_value = None
    target = MusicTarget(tools)
    target.mark_failed(music_request, "Quota")
    target.mark_cancelled(music_request)
    return tools.repository.update_episode


@pytest.fixture
def thumbnail_target_effects(tools, tmp_path):
    request = build_request(GenerationKind.THUMBNAIL, params={"candidate": 3})
    target = ThumbnailTarget(tools)
    old_candidate = write_file(tools.files.thumbnail_candidate_path("p1", "e1", 3, "jpg"))
    output_path = target.output_path(request, "png")
    target.mark_queued(request)
    target.mark_processing(request)
    target.save_result(request, write_file(output_path))
    target.mark_failed(request, "Blocked")
    target.mark_cancelled(request)
    target.on_final(request)
    return SimpleNamespace(
        tools=tools,
        output_path=output_path,
        old_candidate=old_candidate,
        is_ready=target.is_ready(request),
    )


@pytest.fixture
def edit_routing():
    character_target = MagicMock(spec=CharacterReferenceTarget)
    scene_target = MagicMock(spec=SceneImageTarget)
    target = EditImageTarget(character_target, scene_target)
    scene_request = build_request(GenerationKind.EDIT_IMAGE, scene_id="s1")
    character_request = build_request(GenerationKind.EDIT_IMAGE, character_id="c1")
    for request in (scene_request, character_request):
        target.mark_queued(request)
        target.is_ready(request)
        target.mark_processing(request)
        target.output_path(request, "png")
        target.save_result(request, "file")
        target.mark_failed(request, "Blocked")
        target.mark_cancelled(request)
        target.on_final(request)
    return SimpleNamespace(
        character_target=character_target,
        scene_target=scene_target,
        scene_request=scene_request,
        character_request=character_request,
    )


@pytest.fixture
def final_listener(tools, clip_request):
    SceneClipTarget(tools).on_final(clip_request)
    return tools.on_final


@pytest.fixture
def targets_by_kind(tools):
    return build_film_targets(tools)


def test_character_mark_queued_sets_queued(queued_character):
    queued_character.assert_called_once_with("c1", {"reference_status": MediaStatus.QUEUED})


def test_character_mark_processing_sets_processing(processing_character):
    processing_character.assert_called_once_with("c1", {"reference_status": MediaStatus.PROCESSING})


def test_generated_reference_replaces_the_old_file(saved_generated_reference):
    assert saved_generated_reference.values == {
        "reference_status": MediaStatus.DONE,
        "reference_source": ReferenceSource.GENERATED,
        "reference_path": "characters/c1/reference.png",
        "reference_error": None,
        "provider_media": None,
    }
    assert not saved_generated_reference.old_file.exists()
    assert saved_generated_reference.new_file.exists()


def test_edited_reference_is_marked_edited(saved_edited_reference):
    assert saved_edited_reference["reference_source"] is ReferenceSource.EDITED


def test_failed_reference_keeps_an_old_file_done(failed_character):
    assert failed_character.actual == {
        "reference_status": failed_character.expected,
        "reference_error": "Blocked",
    }


def test_cancelled_reference_falls_back_to_its_file(cancelled_character):
    assert cancelled_character.actual == {"reference_status": cancelled_character.expected}


def test_missing_character_is_left_alone(missing_character_updates):
    missing_character_updates.assert_not_called()


def test_scene_image_with_every_reference_done_is_ready(ready_scene_image):
    assert ready_scene_image is True


def test_scene_image_without_a_reference_fails_before_submit(blocked_scene_image):
    assert blocked_scene_image.is_ready is False
    tools = blocked_scene_image.tools
    fields = tools.request_repository.update_fields.call_args.args[1]
    assert fields["status"] is GenerationStatus.FAILED
    assert fields["error_message"] == "Reference image missing for: Mai"
    assert updated_values(tools.repository.update_scene) == {
        "image_status": MediaStatus.FAILED,
        "image_error": "Reference image missing for: Mai",
    }
    tools.on_final.assert_called_once()


def test_scene_edit_needs_no_reference(edit_request_readiness):
    assert edit_request_readiness is True


def test_request_of_a_deleted_scene_is_ready(missing_scene_readiness):
    assert missing_scene_readiness is True


def test_new_scene_image_resets_the_clip(saved_scene_image):
    assert saved_scene_image.values == {
        "image_status": MediaStatus.DONE,
        "image_path": "projects/p1/episodes/e1/scenes/s1/image.png",
        "image_error": None,
        "clip_status": MediaStatus.NONE,
        "clip_path": None,
        "clip_duration_ms": None,
        "trim_start_ms": 1000,
        "trim_end_ms": None,
        "image_source": SceneImageSource.GENERATED,
    }
    assert not saved_scene_image.old_clip.exists()


def test_new_scene_image_deletes_the_segments_of_the_old_image(saved_scene_image):
    assert not saved_scene_image.old_segment.parent.exists()


def test_new_scene_image_on_a_done_episode_needs_assembly(saved_scene_image):
    assert saved_scene_image.episode_values == {"needs_assembly": True}


def test_edited_image_keeps_a_queued_clip_request(saved_edit_with_queued_clip):
    assert saved_edit_with_queued_clip.values["clip_status"] is MediaStatus.QUEUED
    assert saved_edit_with_queued_clip.values["image_source"] is SceneImageSource.EDITED
    saved_edit_with_queued_clip.episode_updates.assert_not_called()


def test_image_of_a_deleted_scene_is_not_saved(save_for_missing_scene):
    save_for_missing_scene.assert_not_called()


def test_failed_scene_image_keeps_an_old_file_done(failed_scene_image):
    assert failed_scene_image.actual == {
        "image_status": failed_scene_image.expected,
        "image_error": "Blocked by the content filter",
    }


def test_cancelled_scene_image_falls_back_to_its_file(cancelled_scene_image):
    assert cancelled_scene_image.actual == {"image_status": cancelled_scene_image.expected}


def test_missing_scene_is_left_alone(missing_scene_updates):
    missing_scene_updates.assert_not_called()


def test_scene_status_follows_the_request(scene_status_updates):
    assert scene_status_updates == [
        ("s1", {"image_status": MediaStatus.QUEUED}),
        ("s1", {"image_status": MediaStatus.PROCESSING}),
    ]


def test_clip_waits_for_the_scene_image(clip_readiness):
    assert clip_readiness.actual is clip_readiness.expected


def test_new_clip_stores_its_length_and_resets_the_trim(saved_clip):
    assert saved_clip.values == {
        "clip_status": MediaStatus.DONE,
        "clip_path": "projects/p1/episodes/e1/scenes/s1/clip.mp4",
        "clip_error": None,
        "trim_start_ms": 1000,
        "trim_end_ms": None,
        "clip_duration_ms": CLIP_DURATION_MS,
    }


def test_narration_stores_the_provider_copy_of_the_voice(narration_with_new_voice_copy):
    repository = narration_with_new_voice_copy.repository
    assert updated_values(repository.update_scene)["narration_duration_ms"] == CLIP_DURATION_MS
    repository.update_voice.assert_called_once_with(
        "v1", {"provider_voices": {"google": "voices/g", "elevenlabs": "voice-x"}}
    )


def test_narration_without_a_new_copy_leaves_the_voice(narration_without_voice_copy):
    narration_without_voice_copy.repository.update_voice.assert_not_called()


def test_music_status_follows_the_request_and_saves_the_track(saved_music):
    assert saved_music == [
        ("e1", {"music_status": MediaStatus.QUEUED}),
        ("e1", {"music_status": MediaStatus.PROCESSING}),
        (
            "e1",
            {
                "music_status": MediaStatus.DONE,
                "music_path": "projects/p1/episodes/e1/music.mp3",
                "music_error": None,
            },
        ),
    ]


def test_failed_music_keeps_an_old_track_done(failed_music):
    assert failed_music.actual == {"music_status": failed_music.expected, "music_error": "Quota"}


def test_cancelled_music_falls_back_to_its_track(cancelled_music):
    assert cancelled_music.actual == {"music_status": cancelled_music.expected}


def test_music_of_a_deleted_episode_is_left_alone(missing_episode_music_updates):
    missing_episode_music_updates.assert_not_called()


def test_thumbnail_candidate_replaces_its_old_file(thumbnail_target_effects):
    assert thumbnail_target_effects.output_path.name == "thumbnail-candidate-3.png"
    assert thumbnail_target_effects.output_path.exists()
    assert not thumbnail_target_effects.old_candidate.exists()
    assert thumbnail_target_effects.is_ready is True


def test_thumbnail_touches_no_episode_and_moves_no_stage(thumbnail_target_effects):
    thumbnail_target_effects.tools.repository.update_episode.assert_not_called()
    thumbnail_target_effects.tools.on_final.assert_not_called()


def test_edit_of_a_scene_goes_to_the_scene_target(edit_routing):
    edit_routing.scene_target.save_result.assert_called_once_with(
        edit_routing.scene_request, "file"
    )
    edit_routing.scene_target.on_final.assert_called_once_with(edit_routing.scene_request)


def test_edit_of_a_character_goes_to_the_character_target(edit_routing):
    edit_routing.character_target.save_result.assert_called_once_with(
        edit_routing.character_request, "file"
    )
    edit_routing.character_target.mark_cancelled.assert_called_once_with(
        edit_routing.character_request
    )


def test_final_request_reaches_the_stage_listener(final_listener, clip_request):
    final_listener.assert_called_once_with(clip_request)


def test_every_film_kind_has_a_target(targets_by_kind):
    assert set(targets_by_kind) == {
        GenerationKind.CHARACTER_IMAGE,
        GenerationKind.SCENE_IMAGE,
        GenerationKind.EDIT_IMAGE,
        GenerationKind.SCENE_CLIP,
        GenerationKind.NARRATION,
        GenerationKind.MUSIC,
        GenerationKind.THUMBNAIL,
    }
