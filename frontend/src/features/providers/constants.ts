import type {
  GenerationMediaKind,
  ImageRouteProviderId,
  MediaKind,
  ProviderDraft,
  ProviderId,
  ProviderKind,
  ProviderStatus,
  RouteName,
  VideoRouteProviderId,
} from "./types";

export interface RouteField {
  route: RouteName;
  label: string;
  providerIds: readonly ProviderId[];
  mediaKinds: readonly GenerationMediaKind[];
  hint?: string;
}

export const PROVIDER_SHORT_NAMES: Record<ProviderId, string> = {
  google_flow: "Google Flow",
  google: "Google AI",
  fal: "fal.ai",
  replicate: "Replicate",
  openai: "OpenAI",
  elevenlabs: "ElevenLabs",
  sd_webui: "Stable Diffusion WebUI / Forge",
  omnivoice: "OmniVoice",
  ace_step: "ACE-Step",
  yue: "YuE",
  claude_cli: "Claude CLI",
};

export const IMAGE_ROUTE_PROVIDER_IDS: readonly ImageRouteProviderId[] = [
  "google_flow",
  "google",
  "fal",
  "replicate",
  "openai",
  "sd_webui",
];

export const VIDEO_ROUTE_PROVIDER_IDS: readonly VideoRouteProviderId[] = ["google_flow", "google", "fal", "replicate"];

export const ROUTE_FIELDS: readonly RouteField[] = [
  {
    route: "image",
    label: "Images",
    providerIds: IMAGE_ROUTE_PROVIDER_IDS,
    mediaKinds: ["image", "edit_image"],
    hint: "Film Clone and Film Studio use it unless they pick their own.",
  },
  {
    route: "video",
    label: "Clips",
    providerIds: VIDEO_ROUTE_PROVIDER_IDS,
    mediaKinds: ["video"],
    hint: "Film Studio uses it unless it picks its own.",
  },
  { route: "speech", label: "Speech", providerIds: ["omnivoice", "elevenlabs", "google"], mediaKinds: ["speech"] },
  { route: "music", label: "Music", providerIds: ["ace_step", "elevenlabs", "yue"], mediaKinds: ["music"] },
];

export const PROVIDER_KIND_LABELS: Record<ProviderKind, string> = {
  api: "API",
  local: "Local",
  extension: "Extension",
  cli: "CLI",
};

export const PROVIDER_STATUS_LABELS: Record<Exclude<ProviderStatus, "paused">, string> = {
  ready: "Ready",
  notSetUp: "Not set up",
  keyUnreadable: "Key unreadable — enter it again",
  connected: "Connected",
  notConnected: "Not connected",
  signedIn: "Signed in",
  notSignedIn: "Not signed in",
  notFound: "CLI not found",
};

export const MODEL_FIELD_LABELS: Record<GenerationMediaKind, string> = {
  image: "Image model",
  edit_image: "Image edit model",
  video: "Clip model",
  speech: "Speech model",
  music: "Music model",
};

export const ANALYSIS_MEDIA_KIND: MediaKind = "analysis";

export const ADAPTER_PROVIDER_IDS: ReadonlySet<ProviderId> = new Set<ProviderId>(["omnivoice", "ace_step", "yue"]);

export const ADAPTER_BASE_URL_HINT = "Run the adapter of tools/local-servers/ and enter its address.";

export const LOCAL_MODEL_LINE = "Uses the model loaded in the server.";

export const IN_USE_BADGE_LABEL = "In use";

export const SECRET_KEY_MISSING_NOTICE = "Set SETTINGS_SECRET_KEY in api/.env to save API keys.";

export const API_KEY_MASK = "••••";

export const CONNECTION_TEST_OK_LABEL = "OK";

export const MAX_CONCURRENT_LOWER_LIMIT = 1;
export const MAX_CONCURRENT_UPPER_LIMIT = 10;
export const MIN_INTERVAL_LOWER_LIMIT_S = 0;
export const MIN_INTERVAL_UPPER_LIMIT_S = 600;

export const EMPTY_PROVIDER_DRAFT: ProviderDraft = { apiKey: "" };

export const PROVIDER_REFRESH_INTERVAL_MS = 5_000;
