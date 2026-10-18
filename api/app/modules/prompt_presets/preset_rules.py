from collections.abc import Collection

from app.modules.prompt_presets.errors import InvalidPresetError
from app.modules.prompt_presets.prompt_texts import (
    PresetPrompts,
    preset_prompts_to_prompts_by_key,
)

MAX_PRESET_NAME_LENGTH = 50
MAX_PROMPT_LENGTH = 20000
KEPT_VERSION_COUNT = 20
FIRST_VERSION = 1
SYSTEM_PRESET_NAME = "Default"
DUPLICATE_SUFFIX_WORD = "copy"
IMPORT_SUFFIX_WORD = "imported"


def to_valid_preset_name(name: str) -> str:
    trimmed_name = name.strip()
    if not 1 <= len(trimmed_name) <= MAX_PRESET_NAME_LENGTH:
        raise InvalidPresetError(f"Preset name must be 1-{MAX_PRESET_NAME_LENGTH} characters")
    return trimmed_name


def validate_preset_prompts(prompts: PresetPrompts) -> None:
    for key, text in preset_prompts_to_prompts_by_key(prompts).items():
        if not 1 <= len(text.strip()) <= MAX_PROMPT_LENGTH:
            raise InvalidPresetError(f"Prompt '{key}' must be 1-{MAX_PROMPT_LENGTH} characters")


def build_unique_preset_name(base_name: str, suffix_word: str, taken_names: Collection[str]) -> str:
    taken_lowercase_names = {name.lower() for name in taken_names}
    attempt = 1
    candidate = _add_name_suffix(base_name, suffix_word, attempt)
    while candidate.lower() in taken_lowercase_names:
        attempt += 1
        candidate = _add_name_suffix(base_name, suffix_word, attempt)
    return candidate


def _add_name_suffix(base_name: str, suffix_word: str, attempt: int) -> str:
    suffix = f" ({suffix_word})" if attempt == 1 else f" ({suffix_word} {attempt})"
    return f"{base_name[: MAX_PRESET_NAME_LENGTH - len(suffix)].rstrip()}{suffix}"
