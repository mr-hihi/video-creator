from collections.abc import Iterable, Mapping
from typing import Any

from app.modules.prompt_presets.prompt_texts import (
    DEFAULT_PRESET_PROMPTS,
    PromptKey,
    preset_prompts_to_prompts_by_key,
)
from app.modules.prompt_presets.service import PresetSnapshot

PRESET_OPTION_KEY = "preset"
PROMPTS_OPTION_KEY = "prompts"

VIDEO_TO_MARKDOWN_PROMPT_KEYS = (PromptKey.VIDEO_TO_MARKDOWN,)
FILM_ANALYSIS_PROMPT_KEYS = (
    PromptKey.VIDEO_TO_MARKDOWN,
    PromptKey.CHARACTER_IMAGE,
    PromptKey.CHARACTER_VOICE,
    PromptKey.SCENE,
)
FILM_PROMPT_PASS_KEYS = (PromptKey.CHARACTER_IMAGE, PromptKey.CHARACTER_VOICE, PromptKey.SCENE)

DEFAULT_PROMPTS_BY_KEY = preset_prompts_to_prompts_by_key(DEFAULT_PRESET_PROMPTS)


def build_prompt_options(
    snapshot: PresetSnapshot, prompt_keys: Iterable[PromptKey]
) -> dict[str, Any]:
    prompts_by_key = preset_prompts_to_prompts_by_key(snapshot.prompts)
    return {
        PRESET_OPTION_KEY: {
            "id": snapshot.preset_id,
            "name": snapshot.name,
            "version": snapshot.version,
        },
        PROMPTS_OPTION_KEY: {key.value: prompts_by_key[key] for key in prompt_keys},
    }


def get_job_prompt(options: Mapping[str, Any], key: PromptKey) -> str:
    stored_prompt = options.get(PROMPTS_OPTION_KEY, {}).get(key.value)
    return stored_prompt or DEFAULT_PROMPTS_BY_KEY[key]
