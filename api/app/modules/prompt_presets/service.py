from dataclasses import dataclass
from typing import BinaryIO
from uuid import uuid4

from app.modules.prompt_presets.errors import (
    PresetConflictError,
    PresetFileTooLargeError,
    PresetVersionNotFoundError,
    PromptPresetNotFoundError,
)
from app.modules.prompt_presets.models import PresetChange, PromptPreset, PromptPresetVersion
from app.modules.prompt_presets.preset_files import (
    MAX_IMPORT_FILE_BYTES,
    PresetDraft,
    export_json_to_preset_draft,
    preset_draft_to_export_json,
    to_export_filename,
)
from app.modules.prompt_presets.preset_rules import (
    DUPLICATE_SUFFIX_WORD,
    FIRST_VERSION,
    IMPORT_SUFFIX_WORD,
    KEPT_VERSION_COUNT,
    MAX_PRESET_NAME_LENGTH,
    SYSTEM_PRESET_NAME,
    build_unique_preset_name,
    to_valid_preset_name,
    validate_preset_prompts,
)
from app.modules.prompt_presets.prompt_texts import (
    DEFAULT_PRESET_PROMPTS,
    PRESET_PROMPT_FIELD_NAMES,
    PresetPrompts,
)
from app.modules.prompt_presets.repository import PromptPresetRepository

MAX_CHANGE_SOURCE_LENGTH = 120


@dataclass(frozen=True)
class PromptPresetDetail:
    preset: PromptPreset
    prompts: PresetPrompts


@dataclass(frozen=True)
class PresetSnapshot:
    preset_id: str
    name: str
    version: int
    prompts: PresetPrompts


@dataclass(frozen=True)
class PresetExport:
    filename: str
    content: str


@dataclass(frozen=True)
class PresetUpload:
    filename: str
    stream: BinaryIO


@dataclass(frozen=True)
class _Revision:
    prompts: PresetPrompts
    change: PresetChange
    change_source: str | None


@dataclass(frozen=True)
class _NewPreset:
    name: str
    revision: _Revision
    is_system: bool


class PromptPresetService:
    def __init__(self, repository: PromptPresetRepository):
        self._repository = repository

    def ensure_default_preset(self) -> None:
        system_preset = self._repository.find_system() or self._add_preset(
            _NewPreset(
                name=SYSTEM_PRESET_NAME,
                revision=_Revision(DEFAULT_PRESET_PROMPTS, PresetChange.CREATED, None),
                is_system=True,
            )
        )
        if self._repository.find_default() is None:
            self._repository.mark_default(system_preset.id)

    def list_presets(self) -> list[PromptPreset]:
        return self._repository.find_all()

    def get_preset_detail(self, preset_id: str) -> PromptPresetDetail:
        preset = self._get_preset(preset_id)
        return PromptPresetDetail(preset=preset, prompts=self._get_current_prompts(preset))

    def create_preset(self, name: str) -> PromptPresetDetail:
        valid_name = to_valid_preset_name(name)
        self._ensure_name_is_free(valid_name, None)
        preset = self._add_preset(
            _NewPreset(
                name=valid_name,
                revision=_Revision(DEFAULT_PRESET_PROMPTS, PresetChange.CREATED, None),
                is_system=False,
            )
        )
        return PromptPresetDetail(preset=preset, prompts=DEFAULT_PRESET_PROMPTS)

    def save_preset(self, preset_id: str, draft: PresetDraft) -> PromptPresetDetail:
        preset = self._get_preset(preset_id)
        valid_name = to_valid_preset_name(draft.name)
        validate_preset_prompts(draft.prompts)
        if valid_name != preset.name:
            self._rename(preset, valid_name)
        if draft.prompts != self._get_current_prompts(preset):
            self._add_version(preset, _Revision(draft.prompts, PresetChange.SAVED, None))
        return self.get_preset_detail(preset_id)

    def delete_preset(self, preset_id: str) -> None:
        preset = self._get_preset(preset_id)
        if preset.is_system:
            raise PresetConflictError(f"The {SYSTEM_PRESET_NAME} preset cannot be deleted")
        if preset.is_default:
            raise PresetConflictError(
                f"Set another preset as default before deleting '{preset.name}'"
            )
        self._repository.delete(preset_id)

    def mark_default_preset(self, preset_id: str) -> PromptPreset:
        self._get_preset(preset_id)
        self._repository.mark_default(preset_id)
        return self._get_preset(preset_id)

    def duplicate_preset(self, preset_id: str) -> PromptPresetDetail:
        source = self.get_preset_detail(preset_id)
        name = build_unique_preset_name(
            source.preset.name, DUPLICATE_SUFFIX_WORD, self._find_taken_names()
        )
        preset = self._add_preset(
            _NewPreset(
                name=name,
                revision=_Revision(
                    source.prompts,
                    PresetChange.DUPLICATED,
                    f"{source.preset.name} v{source.preset.current_version}",
                ),
                is_system=False,
            )
        )
        return PromptPresetDetail(preset=preset, prompts=source.prompts)

    def list_versions(self, preset_id: str) -> list[PromptPresetVersion]:
        self._get_preset(preset_id)
        return self._repository.find_versions(preset_id)

    def get_version(self, preset_id: str, version: int) -> PromptPresetVersion:
        self._get_preset(preset_id)
        preset_version = self._repository.find_version(preset_id, version)
        if preset_version is None:
            raise PresetVersionNotFoundError(preset_id, version)
        return preset_version

    def restore_version(self, preset_id: str, version: int) -> PromptPresetDetail:
        restored = self.get_version(preset_id, version)
        preset = self._get_preset(preset_id)
        self._add_version(
            preset, _Revision(restored.to_preset_prompts(), PresetChange.RESTORED, f"v{version}")
        )
        return self.get_preset_detail(preset_id)

    def export_preset(self, preset_id: str) -> PresetExport:
        detail = self.get_preset_detail(preset_id)
        return PresetExport(
            filename=to_export_filename(detail.preset.name),
            content=preset_draft_to_export_json(
                PresetDraft(name=detail.preset.name, prompts=detail.prompts)
            ),
        )

    def import_preset(self, upload: PresetUpload) -> PromptPresetDetail:
        file_content = upload.stream.read(MAX_IMPORT_FILE_BYTES + 1)
        if len(file_content) > MAX_IMPORT_FILE_BYTES:
            raise PresetFileTooLargeError("Preset file exceeds 1 MB")
        draft = export_json_to_preset_draft(file_content)
        valid_name = to_valid_preset_name(draft.name)
        validate_preset_prompts(draft.prompts)
        preset = self._add_preset(
            _NewPreset(
                name=self._to_free_import_name(valid_name),
                revision=_Revision(
                    draft.prompts,
                    PresetChange.IMPORTED,
                    upload.filename[:MAX_CHANGE_SOURCE_LENGTH],
                ),
                is_system=False,
            )
        )
        return PromptPresetDetail(preset=preset, prompts=draft.prompts)

    def get_job_snapshot(self, preset_id: str | None) -> PresetSnapshot:
        preset = self._get_preset(preset_id) if preset_id else self._get_default_preset()
        return PresetSnapshot(
            preset_id=preset.id,
            name=preset.name,
            version=preset.current_version,
            prompts=self._get_current_prompts(preset),
        )

    def _get_preset(self, preset_id: str) -> PromptPreset:
        preset = self._repository.find_by_id(preset_id)
        if preset is None:
            raise PromptPresetNotFoundError(preset_id)
        return preset

    def _get_default_preset(self) -> PromptPreset:
        preset = self._repository.find_default()
        if preset is None:
            raise PromptPresetNotFoundError("default")
        return preset

    def _get_current_prompts(self, preset: PromptPreset) -> PresetPrompts:
        current_version = self._repository.find_version(preset.id, preset.current_version)
        if current_version is None:
            raise PresetVersionNotFoundError(preset.id, preset.current_version)
        return current_version.to_preset_prompts()

    def _rename(self, preset: PromptPreset, name: str) -> None:
        if preset.is_system:
            raise PresetConflictError(f"The {SYSTEM_PRESET_NAME} preset cannot be renamed")
        self._ensure_name_is_free(name, preset.id)
        self._repository.rename(preset.id, name)

    def _ensure_name_is_free(self, name: str, own_preset_id: str | None) -> None:
        holder = self._repository.find_by_name(name)
        if holder is not None and holder.id != own_preset_id:
            raise PresetConflictError(f"A preset named '{name}' already exists")

    def _find_taken_names(self) -> list[str]:
        return [preset.name for preset in self._repository.find_all()]

    def _to_free_import_name(self, name: str) -> str:
        if self._repository.find_by_name(name) is None:
            return name
        return build_unique_preset_name(name, IMPORT_SUFFIX_WORD, self._find_taken_names())

    def _add_preset(self, new_preset: _NewPreset) -> PromptPreset:
        preset = PromptPreset(
            id=str(uuid4()),
            name=new_preset.name[:MAX_PRESET_NAME_LENGTH],
            is_system=new_preset.is_system,
            is_default=False,
            current_version=FIRST_VERSION,
        )
        first_version = _build_version(preset.id, FIRST_VERSION, new_preset.revision)
        return self._repository.add_preset(preset, first_version)

    def _add_version(self, preset: PromptPreset, revision: _Revision) -> None:
        version = _build_version(preset.id, preset.current_version + 1, revision)
        self._repository.add_version(version, KEPT_VERSION_COUNT)


def _build_version(preset_id: str, version: int, revision: _Revision) -> PromptPresetVersion:
    return PromptPresetVersion(
        id=str(uuid4()),
        preset_id=preset_id,
        version=version,
        change=revision.change,
        change_source=revision.change_source,
        **{
            field_name: getattr(revision.prompts, field_name)
            for field_name in PRESET_PROMPT_FIELD_NAMES
        },
    )
