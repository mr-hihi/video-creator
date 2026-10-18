from dataclasses import dataclass
from enum import StrEnum


class ProviderId(StrEnum):
    GOOGLE_FLOW = "google_flow"
    GOOGLE = "google"
    FAL = "fal"
    REPLICATE = "replicate"
    OPENAI = "openai"
    ELEVENLABS = "elevenlabs"
    SD_WEBUI = "sd_webui"
    OMNIVOICE = "omnivoice"
    ACE_STEP = "ace_step"
    YUE = "yue"
    CLAUDE_CLI = "claude_cli"


class ProviderKind(StrEnum):
    API = "api"
    LOCAL = "local"
    EXTENSION = "extension"
    CLI = "cli"


class MediaKind(StrEnum):
    IMAGE = "image"
    EDIT_IMAGE = "edit_image"
    VIDEO = "video"
    SPEECH = "speech"
    MUSIC = "music"
    ANALYSIS = "analysis"


class MediaFeature(StrEnum):
    FILM_CLONE = "film_clone"
    FILM_STUDIO = "film_studio"


class RouteName(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    SPEECH = "speech"
    MUSIC = "music"


IMAGE_MEDIA_KINDS = (MediaKind.IMAGE, MediaKind.EDIT_IMAGE)
VISUAL_MEDIA_KINDS = (*IMAGE_MEDIA_KINDS, MediaKind.VIDEO)


@dataclass(frozen=True)
class ProviderSpec:
    id: ProviderId
    name: str
    kind: ProviderKind
    media_kinds: tuple[MediaKind, ...]


PROVIDER_SPECS: tuple[ProviderSpec, ...] = (
    ProviderSpec(ProviderId.GOOGLE_FLOW, "Google Flow", ProviderKind.EXTENSION, VISUAL_MEDIA_KINDS),
    ProviderSpec(
        ProviderId.GOOGLE,
        "Google AI (Gemini, Veo)",
        ProviderKind.API,
        (*VISUAL_MEDIA_KINDS, MediaKind.SPEECH, MediaKind.ANALYSIS),
    ),
    ProviderSpec(ProviderId.FAL, "fal.ai", ProviderKind.API, VISUAL_MEDIA_KINDS),
    ProviderSpec(ProviderId.REPLICATE, "Replicate", ProviderKind.API, VISUAL_MEDIA_KINDS),
    ProviderSpec(
        ProviderId.OPENAI, "OpenAI", ProviderKind.API, (*IMAGE_MEDIA_KINDS, MediaKind.ANALYSIS)
    ),
    ProviderSpec(
        ProviderId.ELEVENLABS,
        "ElevenLabs",
        ProviderKind.API,
        (MediaKind.SPEECH, MediaKind.MUSIC),
    ),
    ProviderSpec(
        ProviderId.SD_WEBUI, "Stable Diffusion WebUI / Forge", ProviderKind.LOCAL, IMAGE_MEDIA_KINDS
    ),
    ProviderSpec(ProviderId.OMNIVOICE, "OmniVoice", ProviderKind.LOCAL, (MediaKind.SPEECH,)),
    ProviderSpec(ProviderId.ACE_STEP, "ACE-Step", ProviderKind.LOCAL, (MediaKind.MUSIC,)),
    ProviderSpec(ProviderId.YUE, "YuE", ProviderKind.LOCAL, (MediaKind.MUSIC,)),
    ProviderSpec(ProviderId.CLAUDE_CLI, "Claude CLI", ProviderKind.CLI, (MediaKind.ANALYSIS,)),
)
PROVIDER_SPECS_BY_ID: dict[ProviderId, ProviderSpec] = {spec.id: spec for spec in PROVIDER_SPECS}

ROUTE_CHOICES: dict[RouteName, tuple[ProviderId, ...]] = {
    RouteName.IMAGE: (
        ProviderId.GOOGLE_FLOW,
        ProviderId.GOOGLE,
        ProviderId.FAL,
        ProviderId.REPLICATE,
        ProviderId.OPENAI,
        ProviderId.SD_WEBUI,
    ),
    RouteName.VIDEO: (
        ProviderId.GOOGLE_FLOW,
        ProviderId.GOOGLE,
        ProviderId.FAL,
        ProviderId.REPLICATE,
    ),
    RouteName.SPEECH: (ProviderId.OMNIVOICE, ProviderId.ELEVENLABS, ProviderId.GOOGLE),
    RouteName.MUSIC: (ProviderId.ACE_STEP, ProviderId.ELEVENLABS, ProviderId.YUE),
}
DEFAULT_PROVIDER_BY_ROUTE: dict[RouteName, ProviderId] = {
    route: choices[0] for route, choices in ROUTE_CHOICES.items()
}

GOOGLE_FLOW_MAX_CONCURRENT = 5
GOOGLE_FLOW_MIN_INTERVAL_S = 10
API_MAX_CONCURRENT = 2
LOCAL_MAX_CONCURRENT = 1


@dataclass(frozen=True)
class ProviderPacingDefaults:
    max_concurrent: int
    min_interval_s: int


def default_pacing(spec: ProviderSpec) -> ProviderPacingDefaults:
    if spec.kind is ProviderKind.EXTENSION:
        return ProviderPacingDefaults(GOOGLE_FLOW_MAX_CONCURRENT, GOOGLE_FLOW_MIN_INTERVAL_S)
    if spec.kind is ProviderKind.API:
        return ProviderPacingDefaults(API_MAX_CONCURRENT, 0)
    return ProviderPacingDefaults(LOCAL_MAX_CONCURRENT, 0)
