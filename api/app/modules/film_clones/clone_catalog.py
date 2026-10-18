from dataclasses import dataclass

from app.modules.film_clones.models import AssetKind, CameraAngle, CloneAspect, ShotSize


@dataclass(frozen=True)
class TargetCountry:
    code: str
    name: str
    language: str


TARGET_COUNTRIES = (
    TargetCountry("vn", "Vietnam", "vi"),
    TargetCountry("jp", "Japan", "ja"),
    TargetCountry("kr", "South Korea", "ko"),
    TargetCountry("cn", "China", "zh"),
    TargetCountry("us", "United States", "en"),
    TargetCountry("gb", "United Kingdom", "en"),
    TargetCountry("fr", "France", "fr"),
    TargetCountry("th", "Thailand", "th"),
    TargetCountry("in", "India", "hi"),
    TargetCountry("id", "Indonesia", "id"),
)
TARGET_COUNTRIES_BY_CODE = {country.code: country for country in TARGET_COUNTRIES}
LANGUAGE_NAMES_BY_CODE = {
    "vi": "Vietnamese",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "en": "English",
    "fr": "French",
    "th": "Thai",
    "hi": "Hindi",
    "id": "Indonesian",
}

SHOT_SIZE_LABELS = {
    ShotSize.EXTREME_WIDE: "Extreme wide",
    ShotSize.WIDE: "Wide",
    ShotSize.FULL: "Full",
    ShotSize.MEDIUM: "Medium",
    ShotSize.MEDIUM_CLOSE: "Medium close-up",
    ShotSize.CLOSE_UP: "Close-up",
    ShotSize.EXTREME_CLOSE_UP: "Extreme close-up",
}
CAMERA_ANGLE_LABELS = {
    CameraAngle.EYE_LEVEL: "Eye level",
    CameraAngle.HIGH: "High angle",
    CameraAngle.LOW: "Low angle",
    CameraAngle.BIRDS_EYE: "Bird's-eye",
    CameraAngle.WORMS_EYE: "Worm's-eye",
    CameraAngle.DUTCH: "Dutch angle",
    CameraAngle.OVER_THE_SHOULDER: "Over the shoulder",
    CameraAngle.POV: "POV",
}


@dataclass(frozen=True)
class ReferenceComposition:
    text: str
    aspect: CloneAspect


CHARACTER_COMPOSITION = ReferenceComposition(
    "full body, head to toe, standing straight, centered, front-facing, neutral background",
    CloneAspect.PORTRAIT,
)
VISUAL_ASSET_COMPOSITION = ReferenceComposition(
    "the whole object, angle showing its features, centered, neutral background",
    CloneAspect.PORTRAIT,
)
LOCATION_COMPOSITION = ReferenceComposition(
    "establishing shot of the whole place, level horizon, clear focal point, depth",
    CloneAspect.LANDSCAPE,
)
COMPOSITIONS_BY_KIND = {
    AssetKind.CHARACTER: CHARACTER_COMPOSITION,
    AssetKind.COSTUME: VISUAL_ASSET_COMPOSITION,
    AssetKind.PROP: VISUAL_ASSET_COMPOSITION,
    AssetKind.LOCATION: LOCATION_COMPOSITION,
}


@dataclass(frozen=True)
class LocalizationFlag:
    kinds: frozenset[AssetKind]
    allowed_change: str


APPEARANCE_FLAG = LocalizationFlag(
    frozenset({AssetKind.CHARACTER}),
    "face, skin tone, hair, build — the person reads as from the target country",
)
COSTUME_FLAG = LocalizationFlag(
    frozenset({AssetKind.CHARACTER, AssetKind.COSTUME}), "clothing and accessories"
)
SETTING_FLAG = LocalizationFlag(
    frozenset({AssetKind.LOCATION, AssetKind.PROP}), "architecture, landscape, signs, objects"
)

MAX_ASSETS = 60
UNKNOWN_ORIGIN = "Unknown"
EMPTY_LABEL = "—"
