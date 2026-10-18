import json
from dataclasses import replace
from io import BytesIO
from unittest.mock import MagicMock

import pytest

from app.modules.prompt_presets.errors import (
    InvalidPresetError,
    PresetConflictError,
    PresetFileTooLargeError,
    PresetVersionNotFoundError,
    PromptPresetNotFoundError,
)
from app.modules.prompt_presets.models import PresetChange, PromptPreset, PromptPresetVersion
from app.modules.prompt_presets.preset_files import PresetDraft, preset_draft_to_export_json
from app.modules.prompt_presets.prompt_texts import DEFAULT_PRESET_PROMPTS, PresetPrompts
from app.modules.prompt_presets.repository import PromptPresetRepository
from app.modules.prompt_presets.service import (
    PresetSnapshot,
    PresetUpload,
    PromptPresetService,
)

PRESET_ID = "preset-1"
SYSTEM_ID = "system-1"
EDITED_PROMPTS = replace(DEFAULT_PRESET_PROMPTS, scene="Scene v2")


def build_preset(**overrides) -> PromptPreset:
    fields = {
        "id": PRESET_ID,
        "name": "Anime",
        "is_system": False,
        "is_default": False,
        "current_version": 2,
    }
    return PromptPreset(**{**fields, **overrides})


def build_system_preset() -> PromptPreset:
    return build_preset(id=SYSTEM_ID, name="Default", is_system=True, is_default=True)


def build_version(version: int, prompts: PresetPrompts) -> PromptPresetVersion:
    return PromptPresetVersion(
        id=f"version-{version}",
        preset_id=PRESET_ID,
        version=version,
        change=PresetChange.SAVED,
        change_source=None,
        video_to_markdown=prompts.video_to_markdown,
        character_image=prompts.character_image,
        character_voice=prompts.character_voice,
        scene=prompts.scene,
    )


def capture_error(error_class: type[Exception], action):
    with pytest.raises(error_class) as caught:
        action()
    return caught.value


def to_upload(content: bytes) -> PresetUpload:
    return PresetUpload(filename="Anime.preset.json", stream=BytesIO(content))


def to_export_bytes(name: str) -> bytes:
    return preset_draft_to_export_json(PresetDraft(name=name, prompts=EDITED_PROMPTS)).encode(
        "utf-8"
    )


@pytest.fixture
def repository():
    preset_repository = MagicMock(spec=PromptPresetRepository)
    preset_repository.find_by_id.return_value = build_preset()
    preset_repository.find_version.return_value = build_version(2, DEFAULT_PRESET_PROMPTS)
    preset_repository.find_by_name.return_value = None
    preset_repository.find_all.return_value = [build_system_preset(), build_preset()]
    preset_repository.find_system.return_value = build_system_preset()
    preset_repository.find_default.return_value = build_system_preset()
    preset_repository.add_preset.side_effect = lambda preset, first_version: preset
    return preset_repository


@pytest.fixture
def service(repository):
    return PromptPresetService(repository)


@pytest.fixture
def added_preset(repository):
    return repository.add_preset.call_args.args[0]


@pytest.fixture
def added_first_version(repository):
    return repository.add_preset.call_args.args[1]


@pytest.fixture
def added_version(repository):
    return repository.add_version.call_args.args[0]


@pytest.fixture
def ensured_on_empty_database(service, repository):
    repository.find_system.return_value = None
    repository.find_default.return_value = None
    service.ensure_default_preset()


@pytest.fixture
def ensured_without_default_mark(service, repository):
    repository.find_default.return_value = None
    service.ensure_default_preset()


@pytest.fixture
def ensured_when_complete(service):
    service.ensure_default_preset()


@pytest.fixture
def listed_preset_names(service):
    return [preset.name for preset in service.list_presets()]


@pytest.fixture
def preset_detail(service):
    return service.get_preset_detail(PRESET_ID)


@pytest.fixture
def missing_preset_error(service, repository):
    repository.find_by_id.return_value = None
    return capture_error(PromptPresetNotFoundError, lambda: service.get_preset_detail("nope"))


@pytest.fixture
def missing_current_version_error(service, repository):
    repository.find_version.return_value = None
    return capture_error(PresetVersionNotFoundError, lambda: service.get_preset_detail(PRESET_ID))


@pytest.fixture
def created_detail(service):
    return service.create_preset("  Documentary  ")


@pytest.fixture
def taken_name_error(service, repository):
    repository.find_by_name.return_value = build_preset(id="other")
    return capture_error(PresetConflictError, lambda: service.create_preset("anime"))


@pytest.fixture(params=["   ", "x" * 51])
def invalid_name_error(request, service):
    return capture_error(InvalidPresetError, lambda: service.create_preset(request.param))


@pytest.fixture
def saved_with_new_prompts(service):
    return service.save_preset(PRESET_ID, PresetDraft(name="Anime", prompts=EDITED_PROMPTS))


@pytest.fixture
def saved_with_new_name(service):
    return service.save_preset(
        PRESET_ID, PresetDraft(name="Anime 2", prompts=DEFAULT_PRESET_PROMPTS)
    )


@pytest.fixture
def saved_unchanged(service):
    return service.save_preset(PRESET_ID, PresetDraft(name="Anime", prompts=DEFAULT_PRESET_PROMPTS))


@pytest.fixture
def saved_with_case_change(service, repository):
    repository.find_by_name.return_value = build_preset()
    return service.save_preset(PRESET_ID, PresetDraft(name="ANIME", prompts=DEFAULT_PRESET_PROMPTS))


@pytest.fixture
def rename_system_error(service, repository):
    repository.find_by_id.return_value = build_system_preset()
    draft = PresetDraft(name="Main", prompts=DEFAULT_PRESET_PROMPTS)
    return capture_error(PresetConflictError, lambda: service.save_preset(SYSTEM_ID, draft))


@pytest.fixture
def rename_to_taken_name_error(service, repository):
    repository.find_by_name.return_value = build_preset(id="other", name="Noir")
    draft = PresetDraft(name="Noir", prompts=DEFAULT_PRESET_PROMPTS)
    return capture_error(PresetConflictError, lambda: service.save_preset(PRESET_ID, draft))


@pytest.fixture(params=["  ", "y" * 20001])
def invalid_prompt_error(request, service):
    draft = PresetDraft(name="Anime", prompts=replace(EDITED_PROMPTS, scene=request.param))
    return capture_error(InvalidPresetError, lambda: service.save_preset(PRESET_ID, draft))


@pytest.fixture
def delete_system_error(service, repository):
    repository.find_by_id.return_value = build_system_preset()
    return capture_error(PresetConflictError, lambda: service.delete_preset(SYSTEM_ID))


@pytest.fixture
def delete_default_error(service, repository):
    repository.find_by_id.return_value = build_preset(is_default=True)
    return capture_error(PresetConflictError, lambda: service.delete_preset(PRESET_ID))


@pytest.fixture
def deleted_preset(service):
    service.delete_preset(PRESET_ID)


@pytest.fixture
def marked_preset(service):
    return service.mark_default_preset(PRESET_ID)


@pytest.fixture
def duplicated_detail(service, repository):
    repository.find_all.return_value = [build_preset(), build_preset(id="x", name="Anime (copy)")]
    return service.duplicate_preset(PRESET_ID)


@pytest.fixture
def listed_versions(service, repository):
    repository.find_versions.return_value = [build_version(2, DEFAULT_PRESET_PROMPTS)]
    return service.list_versions(PRESET_ID)


@pytest.fixture
def missing_version_error(service, repository):
    repository.find_version.return_value = None
    return capture_error(PresetVersionNotFoundError, lambda: service.get_version(PRESET_ID, 1))


@pytest.fixture
def restored_detail(service, repository):
    repository.find_version.return_value = build_version(1, EDITED_PROMPTS)
    return service.restore_version(PRESET_ID, 1)


@pytest.fixture
def exported_preset(service):
    return service.export_preset(PRESET_ID)


@pytest.fixture
def imported_with_free_name(service):
    return service.import_preset(to_upload(to_export_bytes("Noir")))


@pytest.fixture
def imported_with_taken_name(service, repository):
    repository.find_by_name.return_value = build_preset()
    return service.import_preset(to_upload(to_export_bytes("Anime")))


@pytest.fixture
def too_large_import_error(service):
    upload = to_upload(b" " * (1024 * 1024 + 1))
    return capture_error(PresetFileTooLargeError, lambda: service.import_preset(upload))


@pytest.fixture
def import_with_empty_prompt_error(service):
    content = to_export_bytes("Noir").replace(b'"Scene v2"', b'""')
    return capture_error(InvalidPresetError, lambda: service.import_preset(to_upload(content)))


@pytest.fixture
def chosen_snapshot(service):
    return service.get_job_snapshot(PRESET_ID)


@pytest.fixture
def default_snapshot(service, repository):
    repository.find_version.return_value = build_version(5, EDITED_PROMPTS)
    return service.get_job_snapshot(None)


@pytest.fixture
def no_default_error(service, repository):
    repository.find_default.return_value = None
    return capture_error(PromptPresetNotFoundError, lambda: service.get_job_snapshot(None))


def test_ensure_default_preset_creates_default_on_an_empty_database(
    ensured_on_empty_database, added_preset, added_first_version, repository
):
    assert (added_preset.name, added_preset.is_system, added_preset.current_version) == (
        "Default",
        True,
        1,
    )
    assert added_first_version.to_preset_prompts() == DEFAULT_PRESET_PROMPTS
    assert added_first_version.change == PresetChange.CREATED
    repository.mark_default.assert_called_once_with(added_preset.id)


def test_ensure_default_preset_gives_the_mark_back_to_default(
    ensured_without_default_mark, repository
):
    repository.add_preset.assert_not_called()
    repository.mark_default.assert_called_once_with(SYSTEM_ID)


def test_ensure_default_preset_changes_nothing_when_complete(ensured_when_complete, repository):
    repository.add_preset.assert_not_called()
    repository.mark_default.assert_not_called()


def test_list_presets_returns_the_repository_order(listed_preset_names):
    assert listed_preset_names == ["Default", "Anime"]


def test_get_preset_detail_reads_the_current_version(preset_detail, repository):
    assert preset_detail.prompts == DEFAULT_PRESET_PROMPTS
    repository.find_version.assert_called_once_with(PRESET_ID, 2)


def test_get_preset_detail_raises_for_an_unknown_preset(missing_preset_error):
    assert str(missing_preset_error) == "Prompt preset nope not found"


def test_get_preset_detail_raises_when_the_current_version_is_gone(
    missing_current_version_error,
):
    assert str(missing_current_version_error) == f"Version 2 of preset {PRESET_ID} not found"


def test_create_preset_starts_from_the_code_defaults(
    created_detail, added_preset, added_first_version
):
    assert added_preset.name == "Documentary"
    assert (added_preset.is_system, added_preset.is_default) == (False, False)
    assert added_first_version.to_preset_prompts() == DEFAULT_PRESET_PROMPTS
    assert (added_first_version.version, added_first_version.change) == (1, PresetChange.CREATED)


def test_create_preset_rejects_a_taken_name(taken_name_error, repository):
    assert str(taken_name_error) == "A preset named 'anime' already exists"
    repository.add_preset.assert_not_called()


def test_create_preset_rejects_an_invalid_name(invalid_name_error):
    assert str(invalid_name_error) == "Preset name must be 1-50 characters"


def test_save_preset_writes_the_next_version(saved_with_new_prompts, added_version, repository):
    assert (added_version.version, added_version.change) == (3, PresetChange.SAVED)
    assert added_version.to_preset_prompts() == EDITED_PROMPTS
    assert repository.add_version.call_args.args[1] == 20
    repository.rename.assert_not_called()


def test_save_preset_renames_without_a_version(saved_with_new_name, repository):
    repository.rename.assert_called_once_with(PRESET_ID, "Anime 2")
    repository.add_version.assert_not_called()


def test_save_preset_writes_nothing_when_unchanged(saved_unchanged, repository):
    repository.rename.assert_not_called()
    repository.add_version.assert_not_called()


def test_save_preset_allows_a_case_change_of_its_own_name(saved_with_case_change, repository):
    repository.rename.assert_called_once_with(PRESET_ID, "ANIME")


def test_save_preset_refuses_to_rename_default(rename_system_error, repository):
    assert str(rename_system_error) == "The Default preset cannot be renamed"
    repository.rename.assert_not_called()


def test_save_preset_refuses_a_name_held_by_another_preset(rename_to_taken_name_error):
    assert str(rename_to_taken_name_error) == "A preset named 'Noir' already exists"


def test_save_preset_rejects_a_blank_or_too_long_prompt(invalid_prompt_error, repository):
    assert str(invalid_prompt_error) == "Prompt 'scene' must be 1-20000 characters"
    repository.add_version.assert_not_called()


def test_delete_preset_refuses_default(delete_system_error, repository):
    assert str(delete_system_error) == "The Default preset cannot be deleted"
    repository.delete.assert_not_called()


def test_delete_preset_refuses_the_default_marked_preset(delete_default_error, repository):
    assert str(delete_default_error) == ("Set another preset as default before deleting 'Anime'")
    repository.delete.assert_not_called()


def test_delete_preset_removes_it(deleted_preset, repository):
    repository.delete.assert_called_once_with(PRESET_ID)


def test_mark_default_preset_moves_the_mark(marked_preset, repository):
    repository.mark_default.assert_called_once_with(PRESET_ID)
    assert marked_preset.id == PRESET_ID


def test_duplicate_preset_takes_the_next_free_copy_name(
    duplicated_detail, added_preset, added_first_version
):
    assert added_preset.name == "Anime (copy 2)"
    assert added_first_version.change == PresetChange.DUPLICATED
    assert added_first_version.change_source == "Anime v2"
    assert duplicated_detail.prompts == DEFAULT_PRESET_PROMPTS


def test_list_versions_returns_the_kept_versions(listed_versions, repository):
    assert [version.version for version in listed_versions] == [2]
    repository.find_versions.assert_called_once_with(PRESET_ID)


def test_get_version_raises_for_a_pruned_version(missing_version_error):
    assert str(missing_version_error) == f"Version 1 of preset {PRESET_ID} not found"


def test_restore_version_writes_a_copy_as_the_next_version(restored_detail, added_version):
    assert (added_version.version, added_version.change, added_version.change_source) == (
        3,
        PresetChange.RESTORED,
        "v1",
    )
    assert added_version.to_preset_prompts() == EDITED_PROMPTS


def test_export_preset_names_the_file_after_the_preset(exported_preset):
    assert exported_preset.filename == "Anime.preset.json"
    assert json.loads(exported_preset.content)["name"] == "Anime"


def test_import_preset_keeps_a_free_name(
    imported_with_free_name, added_preset, added_first_version
):
    assert added_preset.name == "Noir"
    assert added_first_version.to_preset_prompts() == EDITED_PROMPTS
    assert (added_first_version.change, added_first_version.change_source) == (
        PresetChange.IMPORTED,
        "Anime.preset.json",
    )


def test_import_preset_renames_a_taken_name(imported_with_taken_name, added_preset):
    assert added_preset.name == "Anime (imported)"


def test_import_preset_rejects_a_file_over_1_mb(too_large_import_error, repository):
    assert str(too_large_import_error) == "Preset file exceeds 1 MB"
    repository.add_preset.assert_not_called()


def test_import_preset_rejects_an_empty_prompt(import_with_empty_prompt_error):
    assert str(import_with_empty_prompt_error) == "Prompt 'scene' must be 1-20000 characters"


def test_get_job_snapshot_copies_the_chosen_preset(chosen_snapshot):
    assert chosen_snapshot == PresetSnapshot(
        preset_id=PRESET_ID, name="Anime", version=2, prompts=DEFAULT_PRESET_PROMPTS
    )


def test_get_job_snapshot_uses_the_default_preset_without_an_id(default_snapshot):
    assert (default_snapshot.preset_id, default_snapshot.prompts) == (SYSTEM_ID, EDITED_PROMPTS)


def test_get_job_snapshot_raises_without_a_default_preset(no_default_error):
    assert str(no_default_error) == "Prompt preset default not found"


@pytest.fixture
def version_written_before_clone_prompts():
    return build_version(1, DEFAULT_PRESET_PROMPTS).to_preset_prompts()


@pytest.fixture
def version_with_a_film_script():
    version = build_version(1, DEFAULT_PRESET_PROMPTS)
    version.film_script = "My film script"
    return version.to_preset_prompts()


def test_version_without_a_later_prompt_reads_its_code_default(
    version_written_before_clone_prompts,
):
    assert version_written_before_clone_prompts == DEFAULT_PRESET_PROMPTS


def test_version_with_a_later_prompt_reads_its_own_text(version_with_a_film_script):
    assert version_with_a_film_script.film_script == "My film script"
