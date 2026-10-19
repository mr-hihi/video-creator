from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.modules.films.character_service import (
    CHARACTER_DESCRIPTION_LIMIT,
    CHARACTER_NAME_LIMIT,
    VOICE_DESCRIPTION_LIMIT,
)
from app.modules.films.errors import EpisodeStepFailedError
from app.modules.films.models import EntityType
from app.modules.films.part_rules import MAX_PART_SCENES, RECAP_LIMIT
from app.modules.films.reply_values import to_entries, to_seconds_within, to_text
from app.modules.films.scene_rules import (
    MAX_SCENE_CLIP_DURATION_S,
    MIN_SCENE_CLIP_DURATION_S,
    NARRATION_LIMIT,
    SCENE_PROMPT_LIMIT,
)

NO_SCENES_MESSAGE = "{model} returned no scenes"

_STRING = {"type": "string"}
_NULLABLE_STRING = {"type": ["string", "null"]}
SCRIPT_REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "recap": _STRING,
        "characters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": _STRING,
                    "entityType": {"type": "string", "enum": [kind.value for kind in EntityType]},
                    "description": _STRING,
                    "voiceDescription": _NULLABLE_STRING,
                    "referenceFrame": _NULLABLE_STRING,
                },
                "required": [
                    "name",
                    "entityType",
                    "description",
                    "voiceDescription",
                    "referenceFrame",
                ],
            },
        },
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "imagePrompt": _STRING,
                    "videoPrompt": _STRING,
                    "narratorText": _NULLABLE_STRING,
                    "characterNames": {"type": "array", "items": _STRING},
                    "durationS": {"type": "integer"},
                },
                "required": [
                    "imagePrompt",
                    "videoPrompt",
                    "narratorText",
                    "characterNames",
                    "durationS",
                ],
            },
        },
    },
    "required": ["recap", "characters", "scenes"],
}


@dataclass(frozen=True)
class ScriptShape:
    default_clip_duration_s: int
    ai_name: str


@dataclass(frozen=True)
class WrittenCharacter:
    name: str
    entity_type: EntityType
    description: str
    voice_description: str | None
    reference_frame: str | None


@dataclass(frozen=True)
class WrittenScene:
    image_prompt: str
    video_prompt: str
    narrator_text: str | None
    character_names: tuple[str, ...]
    clip_duration_s: int


@dataclass(frozen=True)
class WrittenScript:
    recap: str | None
    characters: tuple[WrittenCharacter, ...]
    scenes: tuple[WrittenScene, ...]


def normalize_script_reply(reply: Mapping[str, Any], shape: ScriptShape) -> WrittenScript:
    scenes = _to_scenes(reply, shape.default_clip_duration_s)[:MAX_PART_SCENES]
    if not scenes:
        raise EpisodeStepFailedError(NO_SCENES_MESSAGE.format(model=shape.ai_name))
    return WrittenScript(
        recap=to_text(reply.get("recap"))[:RECAP_LIMIT] or None,
        characters=_to_characters(reply),
        scenes=scenes,
    )


def to_character_ids(
    character_names: Sequence[str], character_ids_by_name: Mapping[str, str]
) -> list[str]:
    character_ids = [
        character_ids_by_name[name.casefold()]
        for name in character_names
        if name.casefold() in character_ids_by_name
    ]
    return list(dict.fromkeys(character_ids))


def _to_scenes(reply: Mapping[str, Any], default_clip_duration_s: int) -> tuple[WrittenScene, ...]:
    return tuple(
        WrittenScene(
            image_prompt=to_text(entry.get("imagePrompt"))[:SCENE_PROMPT_LIMIT],
            video_prompt=to_text(entry.get("videoPrompt"))[:SCENE_PROMPT_LIMIT],
            narrator_text=to_text(entry.get("narratorText"))[:NARRATION_LIMIT] or None,
            character_names=_to_names(entry.get("characterNames")),
            clip_duration_s=to_seconds_within(
                entry.get("durationS"),
                (MIN_SCENE_CLIP_DURATION_S, MAX_SCENE_CLIP_DURATION_S),
                default_clip_duration_s,
            ),
        )
        for entry in to_entries(reply, "scenes")
        if to_text(entry.get("imagePrompt")) and to_text(entry.get("videoPrompt"))
    )


def _to_characters(reply: Mapping[str, Any]) -> tuple[WrittenCharacter, ...]:
    characters_by_name: dict[str, WrittenCharacter] = {}
    for entry in to_entries(reply, "characters"):
        name = to_text(entry.get("name"))[:CHARACTER_NAME_LIMIT]
        if name and name.casefold() not in characters_by_name:
            characters_by_name[name.casefold()] = _to_character(name, entry)
    return tuple(characters_by_name.values())


def _to_character(name: str, entry: Mapping[str, Any]) -> WrittenCharacter:
    description = to_text(entry.get("description")) or name
    return WrittenCharacter(
        name=name,
        entity_type=_to_entity_type(entry.get("entityType")),
        description=description[:CHARACTER_DESCRIPTION_LIMIT],
        voice_description=to_text(entry.get("voiceDescription"))[:VOICE_DESCRIPTION_LIMIT] or None,
        reference_frame=to_text(entry.get("referenceFrame")) or None,
    )


def _to_entity_type(value: Any) -> EntityType:
    try:
        return EntityType(to_text(value).lower())
    except ValueError:
        return EntityType.CHARACTER


def _to_names(raw_names: Any) -> tuple[str, ...]:
    if not isinstance(raw_names, list):
        return ()
    return tuple(name for name in (to_text(raw_name) for raw_name in raw_names) if name)
