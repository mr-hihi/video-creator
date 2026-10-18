from dataclasses import dataclass

from app.modules.providers.provider_catalog import MediaKind, ProviderId

ALL_CLIP_LENGTHS_S = (4, 6, 8, 10)
VEO_CLIP_LENGTHS_S = (4, 6, 8)
FLOW_VEO_CLIP_LENGTHS_S = (8,)
LOCAL_LONGEST_TRACK_S = 600
CLIP_LENGTH_PLACEHOLDER = "{n}"
CLAUDE_CLI_DEFAULT_MODEL = "default"


@dataclass(frozen=True)
class CatalogModel:
    id: str
    label: str
    max_references: int | None = None
    clip_lengths_s: tuple[int, ...] = ()
    has_sound: bool = True
    longest_track_s: int | None = None
    with_references_id: str | None = None

    def id_for_clip_length(self, clip_length_s: int) -> str:
        return self.id.replace(CLIP_LENGTH_PLACEHOLDER, str(clip_length_s))


FLOW_IMAGE_MODELS = (
    CatalogModel("GEM_PIX_2", "Nano Banana Pro"),
    CatalogModel("NARWHAL", "Nano Banana 2"),
    CatalogModel("HARBOR_SEAL", "Nano Banana 2 Lite"),
)
GOOGLE_IMAGE_MODELS = (
    CatalogModel("gemini-nano-banana-2.1", "Nano Banana 2.1", max_references=14),
    CatalogModel("gemini-3.1-flash-image", "Nano Banana 2", max_references=14),
    CatalogModel("gemini-3-pro-image", "Nano Banana Pro", max_references=11),
)
REPLICATE_IMAGE_MODELS = (
    CatalogModel("google/nano-banana-pro", "Nano Banana Pro", max_references=14),
    CatalogModel("bytedance/seedream-4.5", "Seedream 4.5", max_references=14),
)
OPENAI_IMAGE_MODELS = (
    CatalogModel("gpt-image-2.5-sunburst", "GPT Image 2.5", max_references=4),
    CatalogModel("gpt-image-2.5-flare", "GPT Image 2.5 Flare", max_references=4),
)
ELEVENLABS_MUSIC_TRACK_S = 300

MODEL_CATALOG: dict[ProviderId, dict[MediaKind, tuple[CatalogModel, ...]]] = {
    ProviderId.GOOGLE_FLOW: {
        MediaKind.IMAGE: FLOW_IMAGE_MODELS,
        MediaKind.EDIT_IMAGE: FLOW_IMAGE_MODELS,
        MediaKind.VIDEO: (
            CatalogModel(
                "veo_3_1_i2v_lite", "Veo 3.1 Lite", clip_lengths_s=FLOW_VEO_CLIP_LENGTHS_S
            ),
            CatalogModel(
                "veo_3_1_i2v_lite_low_priority",
                "Veo 3.1 Lite, low priority",
                clip_lengths_s=FLOW_VEO_CLIP_LENGTHS_S,
            ),
            CatalogModel(
                "veo_3_1_i2v_s_fast_ultra", "Veo 3.1 Fast", clip_lengths_s=FLOW_VEO_CLIP_LENGTHS_S
            ),
            CatalogModel("abra_i2v_{n}s", "Omni Flash", clip_lengths_s=ALL_CLIP_LENGTHS_S),
        ),
    },
    ProviderId.GOOGLE: {
        MediaKind.IMAGE: GOOGLE_IMAGE_MODELS,
        MediaKind.EDIT_IMAGE: GOOGLE_IMAGE_MODELS,
        MediaKind.VIDEO: (
            CatalogModel(
                "veo-3.1-lite-generate-preview", "Veo 3.1 Lite", clip_lengths_s=VEO_CLIP_LENGTHS_S
            ),
            CatalogModel(
                "veo-3.1-fast-generate-preview", "Veo 3.1 Fast", clip_lengths_s=VEO_CLIP_LENGTHS_S
            ),
            CatalogModel("veo-3.1-generate-preview", "Veo 3.1", clip_lengths_s=VEO_CLIP_LENGTHS_S),
        ),
        MediaKind.SPEECH: (
            CatalogModel("gemini-3.8-flash-tts", "Gemini 3.8 Flash TTS"),
            CatalogModel("gemini-3.8-flash-lite-tts", "Gemini 3.8 Flash Lite TTS"),
        ),
        MediaKind.ANALYSIS: (
            CatalogModel("gemini-4-argon", "Gemini 4 Argon"),
            CatalogModel("gemini-3.8-flash", "Gemini 3.8 Flash"),
            CatalogModel("gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite"),
        ),
    },
    ProviderId.FAL: {
        MediaKind.IMAGE: (
            CatalogModel(
                "fal-ai/nano-banana-pro",
                "Nano Banana Pro",
                max_references=14,
                with_references_id="fal-ai/nano-banana-pro/edit",
            ),
        ),
        MediaKind.EDIT_IMAGE: (
            CatalogModel("fal-ai/nano-banana-pro/edit", "Nano Banana Pro edit", max_references=14),
            CatalogModel("google/nano-banana-2.1/edit", "Nano Banana 2.1 edit", max_references=14),
            CatalogModel(
                "fal-ai/bytedance/seedream/v4.5/edit", "Seedream 4.5 edit", max_references=10
            ),
            CatalogModel("fal-ai/flux-pro/kontext", "Flux Kontext", max_references=0),
        ),
        MediaKind.VIDEO: (
            CatalogModel(
                "fal-ai/kling-video/v3/pro/image-to-video",
                "Kling 3 Pro",
                clip_lengths_s=ALL_CLIP_LENGTHS_S,
            ),
            CatalogModel(
                "bytedance/seedance-2.5/image-to-video",
                "Seedance 2.5",
                clip_lengths_s=ALL_CLIP_LENGTHS_S,
            ),
        ),
    },
    ProviderId.REPLICATE: {
        MediaKind.IMAGE: REPLICATE_IMAGE_MODELS,
        MediaKind.EDIT_IMAGE: (
            *REPLICATE_IMAGE_MODELS,
            CatalogModel(
                "black-forest-labs/flux-kontext-pro", "Flux Kontext Pro", max_references=0
            ),
        ),
        MediaKind.VIDEO: (
            CatalogModel("kwaivgi/kling-v3-video", "Kling 3", clip_lengths_s=ALL_CLIP_LENGTHS_S),
            CatalogModel("alibaba/wan-3", "Wan 3", clip_lengths_s=ALL_CLIP_LENGTHS_S),
            CatalogModel("google/veo-3.1", "Veo 3.1", clip_lengths_s=VEO_CLIP_LENGTHS_S),
            CatalogModel("google/veo-3.1-fast", "Veo 3.1 Fast", clip_lengths_s=VEO_CLIP_LENGTHS_S),
            CatalogModel(
                "minimax/hailuo-2.3", "Hailuo 2.3", clip_lengths_s=(6, 10), has_sound=False
            ),
        ),
    },
    ProviderId.OPENAI: {
        MediaKind.IMAGE: OPENAI_IMAGE_MODELS,
        MediaKind.EDIT_IMAGE: OPENAI_IMAGE_MODELS,
        MediaKind.ANALYSIS: (
            CatalogModel("gpt-6-astra", "GPT-6 Astra"),
            CatalogModel("gpt-6.1-sol", "GPT-6.1 Sol"),
            CatalogModel("gpt-6-luna", "GPT-6 Luna"),
        ),
    },
    ProviderId.ELEVENLABS: {
        MediaKind.SPEECH: (
            CatalogModel("eleven_v4", "Eleven v4"),
            CatalogModel("eleven_v4_turbo", "Eleven v4 Turbo"),
            CatalogModel("eleven_v3", "Eleven v3"),
            CatalogModel("eleven_flash_v2_5", "Flash 2.5"),
        ),
        MediaKind.MUSIC: (
            CatalogModel("music_v2_5", "Music v2.5", longest_track_s=ELEVENLABS_MUSIC_TRACK_S),
            CatalogModel("music_v2", "Music v2", longest_track_s=ELEVENLABS_MUSIC_TRACK_S),
            CatalogModel("music_v1", "Music v1", longest_track_s=ELEVENLABS_MUSIC_TRACK_S),
        ),
    },
    ProviderId.CLAUDE_CLI: {
        MediaKind.ANALYSIS: (
            CatalogModel(CLAUDE_CLI_DEFAULT_MODEL, "Claude (CLI default)"),
            CatalogModel("fable", "Claude Fable"),
            CatalogModel("opus", "Claude Opus"),
            CatalogModel("sonnet", "Claude Sonnet"),
            CatalogModel("haiku", "Claude Haiku"),
        ),
    },
}
LOCAL_MODELS: dict[ProviderId, dict[MediaKind, CatalogModel]] = {
    ProviderId.SD_WEBUI: {
        MediaKind.IMAGE: CatalogModel("", "Loaded checkpoint"),
        MediaKind.EDIT_IMAGE: CatalogModel("", "Loaded checkpoint"),
    },
    ProviderId.OMNIVOICE: {MediaKind.SPEECH: CatalogModel("", "Loaded model")},
    ProviderId.ACE_STEP: {
        MediaKind.MUSIC: CatalogModel("", "Loaded model", longest_track_s=LOCAL_LONGEST_TRACK_S)
    },
    ProviderId.YUE: {
        MediaKind.MUSIC: CatalogModel("", "Loaded model", longest_track_s=LOCAL_LONGEST_TRACK_S)
    },
}


def find_catalog_models(provider_id: ProviderId, media_kind: MediaKind) -> tuple[CatalogModel, ...]:
    return MODEL_CATALOG.get(provider_id, {}).get(media_kind, ())


def resolve_model(
    provider_id: ProviderId, media_kind: MediaKind, chosen_model_id: str | None
) -> CatalogModel:
    local_model = LOCAL_MODELS.get(provider_id, {}).get(media_kind)
    if local_model is not None:
        return local_model
    models = find_catalog_models(provider_id, media_kind)
    return next((model for model in models if model.id == chosen_model_id), models[0])
