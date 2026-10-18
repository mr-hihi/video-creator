import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.modules.film_clones.clone_catalog import MAX_ASSETS, UNKNOWN_ORIGIN
from app.modules.film_clones.errors import CloneStepFailedError
from app.modules.film_clones.models import AssetKind, CameraAngle, FrameKind, ShotSize
from app.modules.jobs.storage import IMAGES_DIR_NAME

NAME_LIMIT = 100
ORIGIN_LIMIT = 100
DESCRIPTION_LIMIT = 2000
EMOTION_LIMIT = 200
ACTION_LIMIT = 1000
NOTE_LIMIT = 300
DIALOGUE_LIMIT = 2000
IMAGE_PROMPT_LIMIT = 4000
TITLE_LIMIT = 150
SHOTS_LIST_KEY = "shots"
SCENES_LIST_KEY = "scenes"
KIND_SUFFIX_PATTERN = re.compile(
    r"\s*\((?:" + "|".join(kind.value for kind in AssetKind) + r")\)$", re.IGNORECASE
)

_STRING = {"type": "string"}
_STRING_LIST = {"type": "array", "items": _STRING}
ASSETS_REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "assets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": [kind.value for kind in AssetKind]},
                    "name": _STRING,
                    "description": _STRING,
                    "culture": _STRING,
                    "period": _STRING,
                    "frames": _STRING_LIST,
                },
                "required": ["kind", "name", "description", "culture", "period", "frames"],
            },
        }
    },
    "required": ["assets"],
}
SHOTS_REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        SHOTS_LIST_KEY: {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "frame": _STRING,
                    "shotSize": {"type": "string", "enum": [size.value for size in ShotSize]},
                    "cameraAngle": {
                        "type": "string",
                        "enum": [angle.value for angle in CameraAngle],
                    },
                    "emotion": _STRING,
                    "action": _STRING,
                    "assetNames": _STRING_LIST,
                },
                "required": ["frame", "shotSize", "cameraAngle", "emotion", "action", "assetNames"],
            },
        }
    },
    "required": [SHOTS_LIST_KEY],
}
LOCALIZATION_REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "assets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": _STRING,
                    "changed": {"type": "boolean"},
                    "localizedName": _STRING,
                    "localizedDescription": _STRING,
                    "note": _STRING,
                },
                "required": ["name", "changed", "localizedName", "localizedDescription", "note"],
            },
        }
    },
    "required": ["assets"],
}
SCRIPT_REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "title": _STRING,
        "logline": _STRING,
        SCENES_LIST_KEY: {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "shotId": _STRING,
                    "description": _STRING,
                    "dialogue": _STRING,
                    "imagePrompt": _STRING,
                },
                "required": ["shotId", "description", "dialogue", "imagePrompt"],
            },
        },
    },
    "required": ["title", "logline", SCENES_LIST_KEY],
}


@dataclass(frozen=True)
class FrameInfo:
    frame: str
    at_ms: int
    kind: FrameKind


@dataclass(frozen=True)
class ExtractedAsset:
    kind: AssetKind
    name: str
    description: str
    culture: str
    period: str
    frames: list[str]


@dataclass(frozen=True)
class AnalyzedShot:
    frame: FrameInfo
    shot_size: ShotSize | None
    camera_angle: CameraAngle | None
    emotion: str | None
    action: str | None
    asset_names: list[str]


@dataclass(frozen=True)
class LocalizationProposal:
    changed: bool
    localized_name: str | None
    localized_description: str | None
    note: str | None


@dataclass(frozen=True)
class WrittenScene:
    shot_id: str
    description: str
    dialogue: str | None
    image_prompt: str


@dataclass(frozen=True)
class WrittenScript:
    title: str
    logline: str | None
    scenes_by_shot_id: dict[str, WrittenScene]


def normalize_assets(reply: Mapping[str, Any], job_frames: Sequence[str]) -> list[ExtractedAsset]:
    known_frames = set(job_frames)
    seen_keys: set[tuple[str, str]] = set()
    assets: list[ExtractedAsset] = []
    for entry in _entries(reply, "assets"):
        kind = _to_enum(AssetKind, entry.get("kind"))
        name = _text(entry.get("name"))[:NAME_LIMIT]
        if kind is None or not name or (kind, name.casefold()) in seen_keys:
            continue
        seen_keys.add((kind, name.casefold()))
        assets.append(
            ExtractedAsset(
                kind=kind,
                name=name,
                description=(_text(entry.get("description")) or name)[:DESCRIPTION_LIMIT],
                culture=(_text(entry.get("culture")) or UNKNOWN_ORIGIN)[:ORIGIN_LIMIT],
                period=(_text(entry.get("period")) or UNKNOWN_ORIGIN)[:ORIGIN_LIMIT],
                frames=_known_frames(entry.get("frames"), known_frames),
            )
        )
    return assets[:MAX_ASSETS]


def normalize_shots(
    reply: Mapping[str, Any], frames: Sequence[FrameInfo], asset_names: Sequence[str]
) -> list[AnalyzedShot]:
    first_entry_by_frame: dict[str, Mapping[str, Any]] = {}
    for entry in _entries(reply, SHOTS_LIST_KEY):
        first_entry_by_frame.setdefault(to_frame_path(_text(entry.get("frame"))), entry)
    names_by_folded = {name.casefold(): name for name in asset_names}
    return [
        _to_analyzed_shot(frame, first_entry_by_frame.get(frame.frame, {}), names_by_folded)
        for frame in frames
    ]


def find_unmatched_frames(reply: Mapping[str, Any], frames: Sequence[FrameInfo]) -> list[str]:
    known_frames = {frame.frame for frame in frames}
    return [
        _text(entry.get("frame"))
        for entry in _entries(reply, SHOTS_LIST_KEY)
        if to_frame_path(_text(entry.get("frame"))) not in known_frames
    ]


def find_placed_frames(reply: Mapping[str, Any], frames: Sequence[FrameInfo]) -> set[str]:
    known_frames = {frame.frame for frame in frames}
    placed_frames = {
        to_frame_path(_text(entry.get("frame"))) for entry in _entries(reply, SHOTS_LIST_KEY)
    }
    return placed_frames & known_frames


def normalize_localization(
    reply: Mapping[str, Any], candidate_names: Sequence[str]
) -> dict[str, LocalizationProposal]:
    names_by_folded = {name.casefold(): name for name in candidate_names}
    proposals_by_name: dict[str, LocalizationProposal] = {}
    for entry in _entries(reply, "assets"):
        name = _find_named(entry.get("name"), names_by_folded)
        if name is None or name in proposals_by_name:
            continue
        proposals_by_name[name] = _to_proposal(entry, name)
    return {
        name: proposals_by_name.get(name, LocalizationProposal(False, None, None, None))
        for name in candidate_names
    }


@dataclass(frozen=True)
class ExpectedScript:
    shot_ids: Sequence[str]
    fallback_title: str
    ai_name: str


def normalize_script(reply: Mapping[str, Any], expected: ExpectedScript) -> WrittenScript:
    known_shot_ids = set(expected.shot_ids)
    scenes_by_shot_id: dict[str, WrittenScene] = {}
    for entry in _entries(reply, SCENES_LIST_KEY):
        shot_id = _text(entry.get("shotId"))
        description = _text(entry.get("description"))
        image_prompt = _text(entry.get("imagePrompt"))
        is_usable = shot_id in known_shot_ids and description and image_prompt
        if not is_usable or shot_id in scenes_by_shot_id:
            continue
        scenes_by_shot_id[shot_id] = WrittenScene(
            shot_id=shot_id,
            description=description[:DESCRIPTION_LIMIT],
            dialogue=_text(entry.get("dialogue"))[:DIALOGUE_LIMIT] or None,
            image_prompt=image_prompt[:IMAGE_PROMPT_LIMIT],
        )
    missing_count = len(known_shot_ids) - len(scenes_by_shot_id)
    if missing_count:
        raise CloneStepFailedError(
            f"{expected.ai_name} returned no scene for {missing_count} of "
            f"{len(known_shot_ids)} shots"
        )
    return WrittenScript(
        title=(_text(reply.get("title")) or expected.fallback_title)[:TITLE_LIMIT],
        logline=_text(reply.get("logline")) or None,
        scenes_by_shot_id=scenes_by_shot_id,
    )


def join_batch_replies(replies: Sequence[Mapping[str, Any]], list_key: str) -> dict[str, Any]:
    first_reply = replies[0] if replies else {}
    return {
        **first_reply,
        list_key: [entry for reply in replies for entry in _entries(reply, list_key)],
    }


def to_frame_path(frame: str) -> str:
    if not frame or "/" in frame:
        return frame
    return f"{IMAGES_DIR_NAME}/{frame}"


def _to_analyzed_shot(
    frame: FrameInfo, entry: Mapping[str, Any], names_by_folded: Mapping[str, str]
) -> AnalyzedShot:
    asset_names: list[str] = []
    for raw_name in entry.get("assetNames") or []:
        name = _find_named(raw_name, names_by_folded)
        if name is not None and name not in asset_names:
            asset_names.append(name)
    return AnalyzedShot(
        frame=frame,
        shot_size=_to_enum(ShotSize, entry.get("shotSize")),
        camera_angle=_to_enum(CameraAngle, entry.get("cameraAngle")),
        emotion=_text(entry.get("emotion"))[:EMOTION_LIMIT] or None,
        action=_text(entry.get("action"))[:ACTION_LIMIT] or None,
        asset_names=asset_names,
    )


def _to_proposal(entry: Mapping[str, Any], name: str) -> LocalizationProposal:
    localized_description = _text(entry.get("localizedDescription"))[:DESCRIPTION_LIMIT]
    if entry.get("changed") is not True or not localized_description:
        return LocalizationProposal(False, None, None, None)
    return LocalizationProposal(
        changed=True,
        localized_name=(_strip_kind_suffix(_text(entry.get("localizedName"))) or name)[:NAME_LIMIT],
        localized_description=localized_description,
        note=_text(entry.get("note"))[:NOTE_LIMIT] or None,
    )


def _known_frames(raw_frames: Any, known_frames: set[str]) -> list[str]:
    frames: list[str] = []
    for raw_frame in raw_frames or []:
        frame = to_frame_path(_text(raw_frame))
        if frame in known_frames and frame not in frames:
            frames.append(frame)
    return frames


def _entries(reply: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    entries = reply.get(key)
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, Mapping)]


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _find_named(raw_name: Any, names_by_folded: Mapping[str, str]) -> str | None:
    name = _text(raw_name)
    return names_by_folded.get(name.casefold()) or names_by_folded.get(
        _strip_kind_suffix(name).casefold()
    )


def _strip_kind_suffix(name: str) -> str:
    return KIND_SUFFIX_PATTERN.sub("", name)


def _to_enum[EnumT](enum_class: type[EnumT], value: Any) -> EnumT | None:
    try:
        return enum_class(value)
    except ValueError:
        return None
