import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.modules.app_settings.setting_rules import ScriptLanguage
from app.modules.film_clones.clone_catalog import (
    APPEARANCE_FLAG,
    COSTUME_FLAG,
    SETTING_FLAG,
    TARGET_COUNTRIES_BY_CODE,
    LocalizationFlag,
)
from app.modules.film_clones.errors import InvalidCloneRequestError
from app.modules.film_clones.models import (
    CloneAsset,
    CloneImageStatus,
    CloneStatus,
    CloneStep,
    FilmClone,
)

TRANSCRIPT_LANGUAGE_PATTERN = re.compile(r"· Language: ([A-Za-z-]+)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class LocalizationChoices:
    target_country: str | None
    target_setting: str | None
    change_appearance: bool
    change_costume: bool
    change_setting: bool

    @property
    def has_ticked_flag(self) -> bool:
        return self.change_appearance or self.change_costume or self.change_setting


def validate_localization_choices(choices: LocalizationChoices) -> None:
    target_country = choices.target_country
    if target_country is not None and target_country not in TARGET_COUNTRIES_BY_CODE:
        raise InvalidCloneRequestError(f"Unknown country '{target_country}'")
    if choices.has_ticked_flag and target_country is None:
        raise InvalidCloneRequestError(
            "Pick a target country to change appearance, costume or setting"
        )


def to_choice_values(choices: LocalizationChoices) -> dict[str, Any]:
    return {
        "target_country": choices.target_country,
        "target_setting": to_target_setting(choices.target_setting),
        "change_appearance": choices.change_appearance,
        "change_costume": choices.change_costume,
        "change_setting": choices.change_setting,
    }


def to_target_setting(requested_target_setting: str | None) -> str | None:
    return (requested_target_setting or "").strip() or None


def to_localization_values(
    choices: LocalizationChoices, script_language: str | None
) -> dict[str, Any]:
    return {
        **to_choice_values(choices),
        "script_language": script_language,
        "status": CloneStatus.RUNNING,
        "step": CloneStep.PROPOSING if choices.has_ticked_flag else CloneStep.WRITING_SCRIPT,
        "error_message": None,
    }


def clone_to_localization_choices(clone: FilmClone) -> LocalizationChoices:
    return LocalizationChoices(
        target_country=clone.target_country,
        target_setting=clone.target_setting,
        change_appearance=clone.change_appearance,
        change_costume=clone.change_costume,
        change_setting=clone.change_setting,
    )


def find_ticked_flags(clone: FilmClone) -> list[LocalizationFlag]:
    flags_with_ticks = (
        (APPEARANCE_FLAG, clone.change_appearance),
        (COSTUME_FLAG, clone.change_costume),
        (SETTING_FLAG, clone.change_setting),
    )
    return [flag for flag, is_ticked in flags_with_ticks if is_ticked]


def find_candidates(
    assets: Sequence[CloneAsset], flags: Sequence[LocalizationFlag]
) -> list[CloneAsset]:
    changeable_kinds = {kind for flag in flags for kind in flag.kinds}
    return [asset for asset in assets if asset.kind in changeable_kinds]


def find_assets_missing_reference(assets: Sequence[CloneAsset]) -> list[CloneAsset]:
    return [
        asset
        for asset in assets
        if asset.changed and asset.reference_status is not CloneImageStatus.DONE
    ]


def resolve_script_language(
    setting: ScriptLanguage, target_country: str | None, transcript_language: str | None
) -> str | None:
    if setting is not ScriptLanguage.FOLLOW_TARGET_COUNTRY:
        return setting.value
    if target_country is not None:
        return TARGET_COUNTRIES_BY_CODE[target_country].language
    return transcript_language


def find_transcript_language(video_notes: str | None) -> str | None:
    if not video_notes:
        return None
    match = TRANSCRIPT_LANGUAGE_PATTERN.search(video_notes)
    return match.group(1).lower()[:3] if match else None
