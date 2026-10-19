import json
from dataclasses import dataclass
from typing import Any

from app.common.filenames import to_safe_file_stem
from app.modules.prompt_presets.errors import InvalidPresetError
from app.modules.prompt_presets.prompt_texts import (
    DEFAULT_PRESET_PROMPTS,
    PresetPrompts,
    PromptKey,
    preset_prompts_to_prompts_by_key,
    prompts_by_key_to_preset_prompts,
)

EXPORT_FORMAT = "video-tool-prompt-preset"
EXPORT_FORMAT_VERSION = 4
FIRST_FORMAT_PROMPT_KEYS = (
    PromptKey.VIDEO_TO_MARKDOWN,
    PromptKey.CHARACTER_IMAGE,
    PromptKey.CHARACTER_VOICE,
    PromptKey.SCENE,
)
SECOND_FORMAT_PROMPT_KEYS = (*FIRST_FORMAT_PROMPT_KEYS, PromptKey.FILM_SCRIPT)
CLONE_PROMPT_KEYS = (
    PromptKey.CLONE_ASSETS,
    PromptKey.CLONE_SHOTS,
    PromptKey.CLONE_LOCALIZATION,
    PromptKey.CLONE_SCRIPT,
)
PROMPT_KEYS_BY_FORMAT_VERSION: dict[int, tuple[PromptKey, ...]] = {
    1: FIRST_FORMAT_PROMPT_KEYS,
    2: SECOND_FORMAT_PROMPT_KEYS,
    3: (*SECOND_FORMAT_PROMPT_KEYS, *CLONE_PROMPT_KEYS),
    EXPORT_FORMAT_VERSION: tuple(PromptKey),
}
DEFAULT_PROMPTS_BY_KEY = preset_prompts_to_prompts_by_key(DEFAULT_PRESET_PROMPTS)
EXPORT_FILE_SUFFIX = ".preset.json"
FALLBACK_EXPORT_STEM = "preset"
NOT_A_PRESET_FILE_MESSAGE = "Not a prompt preset file"
MAX_IMPORT_FILE_BYTES = 1024 * 1024


@dataclass(frozen=True)
class PresetDraft:
    name: str
    prompts: PresetPrompts


def preset_draft_to_export_json(draft: PresetDraft) -> str:
    prompts_by_key = preset_prompts_to_prompts_by_key(draft.prompts)
    payload = {
        "format": EXPORT_FORMAT,
        "formatVersion": EXPORT_FORMAT_VERSION,
        "name": draft.name,
        "prompts": {key.value: text for key, text in prompts_by_key.items()},
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def to_export_filename(preset_name: str) -> str:
    return f"{to_safe_file_stem(preset_name, FALLBACK_EXPORT_STEM)}{EXPORT_FILE_SUFFIX}"


def export_json_to_preset_draft(file_content: bytes) -> PresetDraft:
    try:
        payload = json.loads(file_content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidPresetError(NOT_A_PRESET_FILE_MESSAGE) from error
    if not _is_preset_payload(payload):
        raise InvalidPresetError(NOT_A_PRESET_FILE_MESSAGE)
    file_prompt_keys = PROMPT_KEYS_BY_FORMAT_VERSION[payload["formatVersion"]]
    prompts = payload["prompts"]
    return PresetDraft(
        name=payload["name"],
        prompts=prompts_by_key_to_preset_prompts(
            {
                key: prompts[key.value] if key in file_prompt_keys else DEFAULT_PROMPTS_BY_KEY[key]
                for key in PromptKey
            }
        ),
    )


def _is_preset_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    file_prompt_keys = PROMPT_KEYS_BY_FORMAT_VERSION.get(payload.get("formatVersion"))
    prompts = payload.get("prompts")
    return (
        payload.get("format") == EXPORT_FORMAT
        and file_prompt_keys is not None
        and isinstance(payload.get("name"), str)
        and isinstance(prompts, dict)
        and all(isinstance(prompts.get(key.value), str) for key in file_prompt_keys)
    )
