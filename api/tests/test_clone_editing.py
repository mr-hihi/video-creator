from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.film_clones.clone_access import CloneAccess
from app.modules.film_clones.clone_files import CloneFiles
from app.modules.film_clones.clone_generation import (
    CloneImageQueue,
    CloneReferenceTarget,
    CloneSceneImageTarget,
    build_scene_image_prompt,
)
from app.modules.film_clones.editing import (
    CloneEditingService,
    CloneEditingTools,
    LocalizedAssetChanges,
    OriginalAssetChanges,
    SceneChanges,
)
from app.modules.film_clones.errors import (
    CloneConflictError,
    CloneFileNotFoundError,
    InvalidCloneRequestError,
)
from app.modules.film_clones.models import (
    AssetKind,
    CameraAngle,
    CloneAspect,
    CloneAsset,
    CloneImageStatus,
    CloneScene,
    CloneShot,
    CloneStatus,
    CloneStep,
    FilmClone,
    FrameKind,
    ShotSize,
)
from app.modules.film_clones.repository import FilmCloneRepository
from app.modules.jobs.storage import JobStorage
from app.modules.media_generation.models import GenerationKind, GenerationRequest
from app.modules.media_generation.service import GenerationService
from app.modules.providers.provider_catalog import MediaKind

CLONE_ID = "clone-1"


def build_clone(status: CloneStatus, step: CloneStep) -> FilmClone:
    return FilmClone(
        id=CLONE_ID,
        job_id="job-1",
        status=status,
        step=step,
        aspect=CloneAspect.LANDSCAPE,
    )


def build_asset(name: str, **overrides) -> CloneAsset:
    fields = {
        "id": f"asset-{name}",
        "clone_id": CLONE_ID,
        "kind": AssetKind.PROP,
        "name": name,
        "description": f"{name} in the film",
        "changed": False,
        "localized_name": None,
        "localized_description": None,
        "reference_status": CloneImageStatus.NONE,
        "reference_path": None,
    }
    return CloneAsset(**{**fields, **overrides})


def build_scene(**overrides) -> CloneScene:
    fields = {
        "id": "scene-1",
        "clone_id": CLONE_ID,
        "shot_id": "shot-1",
        "position": 2,
        "description": "He runs",
        "dialogue": None,
        "image_prompt": "A scholar running across a citadel courtyard",
        "image_status": CloneImageStatus.DONE,
        "image_path": "clone-1/scenes/scene-1.png",
    }
    return CloneScene(**{**fields, **overrides})


def build_shot(**overrides) -> CloneShot:
    fields = {
        "id": "shot-1",
        "clone_id": CLONE_ID,
        "position": 2,
        "at_ms": 40000,
        "frame": "images/moment-03-00m40s.jpg",
        "frame_kind": FrameKind.SCENE,
        "shot_size": ShotSize.WIDE,
        "camera_angle": CameraAngle.HIGH,
    }
    return CloneShot(**{**fields, **overrides})


def build_editing(clone: FilmClone, assets=(), open_requests=(), scene=None):
    repository = MagicMock(spec=FilmCloneRepository)
    repository.find_by_id.return_value = clone
    assets_by_id = {asset.id: asset for asset in assets}
    repository.find_asset.side_effect = assets_by_id.get
    repository.find_assets.return_value = list(assets)
    repository.find_scene.return_value = scene
    repository.find_shot.return_value = build_shot()
    generation_service = MagicMock(spec=GenerationService)
    generation_service.find_open_for_clone.return_value = list(open_requests)
    image_queue = MagicMock(spec=CloneImageQueue)
    files = MagicMock(spec=CloneFiles)
    service = CloneEditingService(
        CloneEditingTools(repository=repository, files=files, image_queue=image_queue),
        CloneAccess(repository, generation_service),
    )
    return SimpleNamespace(service=service, repository=repository, files=files, queue=image_queue)


def capture(error_class, call):
    with pytest.raises(error_class) as caught:
        call()
    return caught.value


CHOOSING = build_clone(CloneStatus.WAITING, CloneStep.CHOOSING_LOCALIZATION)
REVIEWING = build_clone(CloneStatus.WAITING, CloneStep.REVIEWING)
A1 = build_asset("Lantern")
A2 = build_asset("Palace", kind=AssetKind.LOCATION)
FAN = build_asset("Fan")
CHANGED_PALACE = build_asset(
    "Palace",
    kind=AssetKind.LOCATION,
    changed=True,
    localized_name="Hue citadel",
    localized_description="An imperial citadel in Hue",
    reference_status=CloneImageStatus.DONE,
    reference_path="clone-1/references/asset-Palace.png",
)


@pytest.fixture
def duplicate_name_error():
    editing = build_editing(CHOOSING, [A1, A2])
    return capture(
        CloneConflictError,
        lambda: editing.service.update_original_asset(A2.id, OriginalAssetChanges(name="LANTERN")),
    )


@pytest.fixture
def blank_culture_error():
    editing = build_editing(CHOOSING, [A1, A2])
    return capture(
        InvalidCloneRequestError,
        lambda: editing.service.update_original_asset(A2.id, OriginalAssetChanges(culture="   ")),
    )


@pytest.fixture
def renamed():
    editing = build_editing(CHOOSING, [A1, A2])
    editing.service.update_original_asset(
        A2.id,
        OriginalAssetChanges(name=" Old Palace ", culture="Korean", period="Joseon dynasty"),
    )
    return editing.repository.update_asset.call_args.args


@pytest.fixture
def late_edit_error():
    editing = build_editing(REVIEWING, [A1])
    return capture(
        CloneConflictError,
        lambda: editing.service.update_original_asset(A1.id, OriginalAssetChanges(name="Lamp")),
    )


@pytest.fixture
def deleted_asset():
    editing = build_editing(CHOOSING, [A1])
    editing.service.delete_asset(A1.id)
    return editing


@pytest.fixture
def undescribed_change_error():
    editing = build_editing(REVIEWING, [FAN])
    return capture(
        InvalidCloneRequestError,
        lambda: editing.service.update_localized_asset(FAN.id, LocalizedAssetChanges(changed=True)),
    )


@pytest.fixture
def changed_fan():
    editing = build_editing(REVIEWING, [FAN])
    editing.service.update_localized_asset(
        FAN.id, LocalizedAssetChanges(changed=True, localized_description=" A paper uchiwa fan ")
    )
    return editing.repository.update_asset.call_args.args


@pytest.fixture
def busy_fan_error():
    changed = build_asset("Fan", changed=True, localized_name="Fan", localized_description="Uchiwa")
    editing = build_editing(
        REVIEWING,
        [changed],
        [GenerationRequest(id="r-1", clone_asset_id=changed.id)],
    )
    return capture(
        CloneConflictError,
        lambda: editing.service.update_localized_asset(
            changed.id, LocalizedAssetChanges(localized_name="Uchiwa")
        ),
    )


@pytest.fixture
def kept_original():
    editing = build_editing(REVIEWING, [CHANGED_PALACE])
    editing.service.update_localized_asset(CHANGED_PALACE.id, LocalizedAssetChanges(changed=False))
    return editing


@pytest.fixture
def unchanged_reference_error():
    editing = build_editing(REVIEWING, [A2])
    return capture(CloneConflictError, lambda: editing.service.generate_reference(A2.id))


@pytest.fixture
def unchanged_rename_error():
    editing = build_editing(REVIEWING, [A2])
    return capture(
        CloneConflictError,
        lambda: editing.service.update_localized_asset(
            A2.id, LocalizedAssetChanges(localized_name="Citadel")
        ),
    )


@pytest.fixture
def queued_reference():
    editing = build_editing(REVIEWING, [CHANGED_PALACE])
    editing.service.generate_reference(CHANGED_PALACE.id)
    return editing


@pytest.fixture
def scene_edit():
    editing = build_editing(
        build_clone(CloneStatus.DONE, CloneStep.GENERATING_SCENE_IMAGES), scene=build_scene()
    )
    editing.service.update_scene(
        "scene-1", SceneChanges(description=" He hides ", dialogue="  ", image_prompt="New prompt")
    )
    return editing.repository.update_scene.call_args.args


@pytest.fixture(
    params=[
        (SceneChanges(description=" "), "Description must be 1-2000 characters"),
        (SceneChanges(dialogue="d" * 2001), "Dialogue must be at most 2000 characters"),
        (SceneChanges(image_prompt="p" * 4001), "Image prompt must be 1-4000 characters"),
    ]
)
def scene_field_error(request):
    changes, expected = request.param
    editing = build_editing(
        build_clone(CloneStatus.FAILED, CloneStep.GENERATING_SCENE_IMAGES), scene=build_scene()
    )
    error = capture(
        InvalidCloneRequestError, lambda: editing.service.update_scene("scene-1", changes)
    )
    return SimpleNamespace(error=error, expected=expected)


@pytest.fixture
def early_scene_edit_error():
    editing = build_editing(
        build_clone(CloneStatus.RUNNING, CloneStep.GENERATING_SCENE_IMAGES), scene=build_scene()
    )
    return capture(
        CloneConflictError,
        lambda: editing.service.update_scene("scene-1", SceneChanges(description="x")),
    )


@pytest.fixture
def busy_scene_error():
    editing = build_editing(
        build_clone(CloneStatus.DONE, CloneStep.GENERATING_SCENE_IMAGES),
        scene=build_scene(image_status=CloneImageStatus.QUEUED),
    )
    return capture(CloneConflictError, lambda: editing.service.generate_scene_image("scene-1"))


@pytest.fixture
def queued_scene_image():
    editing = build_editing(
        build_clone(CloneStatus.FAILED, CloneStep.GENERATING_SCENE_IMAGES), scene=build_scene()
    )
    editing.service.generate_scene_image("scene-1")
    return editing.queue.queue_scene_image.call_args.args


@pytest.fixture
def queued_orders(tmp_path):
    generation_service = MagicMock(spec=GenerationService)
    queue = CloneImageQueue(generation_service, JobStorage(tmp_path, 1024))
    clone = build_clone(CloneStatus.WAITING, CloneStep.REVIEWING)
    queue.queue_reference(clone, CHANGED_PALACE)
    queue.queue_scene_image(clone, build_scene(), build_shot())
    return [call.args[0] for call in generation_service.queue.call_args_list]


@pytest.fixture(
    params=[
        (ShotSize.WIDE, CameraAngle.HIGH, "P Shot: Wide, High angle."),
        (None, CameraAngle.POV, "P Shot: POV."),
        (None, None, "P"),
    ]
)
def scene_prompt(request):
    shot_size, camera_angle, expected = request.param
    prompt = build_scene_image_prompt(
        build_scene(image_prompt="P"), build_shot(shot_size=shot_size, camera_angle=camera_angle)
    )
    return SimpleNamespace(actual=prompt, expected=expected)


def run_reference_target(tmp_path, asset: CloneAsset, action: str):
    repository = MagicMock(spec=FilmCloneRepository)
    repository.find_asset.return_value = asset
    files = CloneFiles(tmp_path)
    target = CloneReferenceTarget(repository, files, MagicMock())
    request = GenerationRequest(
        id="r-1",
        kind=GenerationKind.CLONE_REFERENCE_IMAGE,
        clone_id=CLONE_ID,
        clone_asset_id=asset.id,
    )
    if action == "save":
        old_file = files.reference_path(CLONE_ID, asset.id, "jpg")
        old_file.parent.mkdir(parents=True)
        old_file.write_bytes(b"old")
        new_file = target.output_path(request, "png")
        new_file.write_bytes(b"new")
        target.save_result(request, new_file)
    elif action == "fail":
        target.mark_failed(request, "Blocked by the content filter")
    else:
        target.mark_cancelled(request)
    return SimpleNamespace(repository=repository, files=files)


@pytest.fixture
def saved_reference(tmp_path):
    return run_reference_target(tmp_path, CHANGED_PALACE, "save")


@pytest.fixture
def failed_first_reference(tmp_path):
    return run_reference_target(tmp_path, build_asset("Fan", changed=True), "fail")


@pytest.fixture
def failed_regenerated_reference(tmp_path):
    return run_reference_target(tmp_path, CHANGED_PALACE, "fail")


@pytest.fixture
def cancelled_first_reference(tmp_path):
    return run_reference_target(tmp_path, build_asset("Fan", changed=True), "cancel")


def finish_reference(tmp_path, clone_id: str | None) -> MagicMock:
    check = MagicMock()
    target = CloneReferenceTarget(MagicMock(spec=FilmCloneRepository), CloneFiles(tmp_path), check)
    target.on_final(GenerationRequest(id="r-1", clone_id=clone_id, clone_asset_id="asset-1"))
    return check


@pytest.fixture
def final_reference(tmp_path):
    return finish_reference(tmp_path, CLONE_ID)


@pytest.fixture
def final_reference_without_clone(tmp_path):
    return finish_reference(tmp_path, None)


@pytest.fixture
def final_scene_image(tmp_path):
    repository = MagicMock(spec=FilmCloneRepository)
    check = MagicMock()
    target = CloneSceneImageTarget(repository, CloneFiles(tmp_path), check)
    target.on_final(GenerationRequest(id="r-1", clone_id=CLONE_ID, clone_scene_id="scene-1"))
    return check


def test_duplicate_asset_name_is_refused(duplicate_name_error):
    assert str(duplicate_name_error) == "An asset named 'LANTERN' already exists in this clone"


def test_blank_culture_is_refused(blank_culture_error):
    assert str(blank_culture_error) == "Culture and period must be 1-100 characters"


def test_original_fields_are_saved_trimmed(renamed):
    assert renamed == (
        A2.id,
        {"name": "Old Palace", "culture": "Korean", "period": "Joseon dynasty"},
    )


def test_original_fields_lock_after_localization(late_edit_error):
    assert str(late_edit_error) == "Assets can be edited only before localization"


def test_deleting_an_asset_removes_it_from_shots(deleted_asset):
    deleted_asset.repository.delete_asset.assert_called_once_with(A1)


def test_change_without_description_is_refused(undescribed_change_error):
    assert str(undescribed_change_error) == "Describe the localized asset first"


def test_change_this_keeps_the_original_name(changed_fan):
    assert changed_fan == (
        FAN.id,
        {"changed": True, "localized_name": "Fan", "localized_description": "A paper uchiwa fan"},
    )


def test_asset_with_generation_running_is_locked(busy_fan_error):
    assert str(busy_fan_error) == "Asset 'Fan' has generation running"


def test_keep_original_clears_the_localization_and_its_file(kept_original):
    kept_original.files.delete.assert_called_once_with("clone-1/references/asset-Palace.png")
    asset_id, values = kept_original.repository.update_asset.call_args.args
    assert values["changed"] is False
    assert values["localized_name"] is None
    assert values["reference_status"] is CloneImageStatus.NONE


def test_unchanged_asset_gets_no_reference(unchanged_reference_error):
    assert str(unchanged_reference_error) == "Asset 'Palace' is not changed"


def test_unchanged_asset_cannot_be_renamed(unchanged_rename_error):
    assert str(unchanged_rename_error) == "Asset 'Palace' is not changed"


def test_reference_of_a_changed_asset_is_queued(queued_reference):
    queued_reference.queue.queue_reference.assert_called_once_with(REVIEWING, CHANGED_PALACE)


def test_scene_text_is_saved_trimmed(scene_edit):
    assert scene_edit == (
        "scene-1",
        {"description": "He hides", "dialogue": None, "image_prompt": "New prompt"},
    )


def test_scene_fields_are_checked(scene_field_error):
    assert str(scene_field_error.error) == scene_field_error.expected


def test_scenes_lock_until_the_script_is_written(early_scene_edit_error):
    assert str(early_scene_edit_error) == "Scenes can be edited once the script is written"


def test_scene_with_generation_running_is_locked(busy_scene_error):
    assert str(busy_scene_error) == "Scene 3 has generation running"


def test_scene_image_is_queued_with_its_shot(queued_scene_image):
    clone, scene, shot = queued_scene_image
    assert (clone.id, scene.id, shot.id) == (CLONE_ID, "scene-1", "shot-1")


def test_reference_order_uses_the_kind_composition(queued_orders):
    reference_order = queued_orders[0]
    assert reference_order.kind is GenerationKind.CLONE_REFERENCE_IMAGE
    assert reference_order.media_kind is MediaKind.IMAGE
    assert reference_order.prompt == (
        "Reference image of An imperial citadel in Hue. establishing shot of the whole place, "
        "level horizon, clear focal point, depth"
    )
    assert reference_order.params == {"aspect": "16:9"}
    assert reference_order.input_paths == {}


def test_scene_order_sends_the_original_frame_only(queued_orders, tmp_path):
    scene_order = queued_orders[1]
    assert scene_order.kind is GenerationKind.CLONE_SCENE_IMAGE
    assert scene_order.media_kind is MediaKind.EDIT_IMAGE
    assert scene_order.input_paths == {
        "sourceImage": str(tmp_path / "job-1" / "output" / "images" / "moment-03-00m40s.jpg")
    }
    assert scene_order.params == {"aspect": "16:9"}
    assert scene_order.prompt.endswith("Shot: Wide, High angle.")


def test_scene_prompt_adds_only_the_set_shot_values(scene_prompt):
    assert scene_prompt.actual == scene_prompt.expected


def test_saved_reference_replaces_the_old_file(saved_reference, tmp_path):
    reference_dir = tmp_path / "film-clones" / CLONE_ID / "references"
    assert sorted(path.name for path in reference_dir.iterdir()) == ["asset-Palace.png"]
    saved_reference.repository.update_asset.assert_called_once_with(
        "asset-Palace",
        {
            "reference_status": CloneImageStatus.DONE,
            "reference_path": "clone-1/references/asset-Palace.png",
            "reference_error": None,
        },
    )


def test_failed_first_reference_shows_the_error(failed_first_reference):
    failed_first_reference.repository.update_asset.assert_called_once_with(
        "asset-Fan",
        {
            "reference_status": CloneImageStatus.FAILED,
            "reference_error": "Blocked by the content filter",
        },
    )


def test_failed_regenerate_keeps_the_old_reference(failed_regenerated_reference):
    failed_regenerated_reference.repository.update_asset.assert_called_once_with(
        "asset-Palace",
        {
            "reference_status": CloneImageStatus.DONE,
            "reference_error": "Blocked by the content filter",
        },
    )


def test_cancelled_first_reference_returns_to_none(cancelled_first_reference):
    cancelled_first_reference.repository.update_asset.assert_called_once_with(
        "asset-Fan", {"reference_status": CloneImageStatus.NONE}
    )


def test_final_reference_checks_the_clone(final_reference):
    final_reference.assert_called_once_with(CLONE_ID)


def test_final_reference_without_clone_checks_nothing(final_reference_without_clone):
    final_reference_without_clone.assert_not_called()


def test_final_scene_image_checks_the_clone(final_scene_image):
    final_scene_image.assert_called_once_with(CLONE_ID)


@pytest.fixture
def clone_files(tmp_path):
    files = CloneFiles(tmp_path)
    scene_file = files.scene_path(CLONE_ID, "scene-1", "png")
    scene_file.parent.mkdir(parents=True)
    scene_file.write_bytes(b"png")
    (tmp_path / "secret.txt").write_text("secret")
    return files


@pytest.fixture(params=["../secret.txt", "clone-1/scenes/missing.png"])
def unreachable_file_error(request, clone_files):
    return capture(CloneFileNotFoundError, lambda: clone_files.resolve_existing(request.param))


def test_clone_file_resolves_inside_the_clone_folder(clone_files, tmp_path):
    assert (
        clone_files.resolve_existing("clone-1/scenes/scene-1.png")
        == (tmp_path / "film-clones" / CLONE_ID / "scenes" / "scene-1.png").resolve()
    )


def test_file_outside_the_folder_or_missing_is_not_found(unreachable_file_error):
    assert str(unreachable_file_error).startswith("File ")
