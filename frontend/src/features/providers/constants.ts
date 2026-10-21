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
  helpText: string;
}

export const PROVIDER_NAME_PLACEHOLDER = "{name}";

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
    helpText:
      "The provider of every image of Film Clone and Film Studio, unless their own tab picks another. A queued image keeps the provider it was given.",
  },
  {
    route: "video",
    label: "Clips",
    providerIds: VIDEO_ROUTE_PROVIDER_IDS,
    mediaKinds: ["video"],
    hint: "Film Studio uses it unless it picks its own.",
    helpText:
      "The provider of every clip of Film Studio, unless the Film Studio tab picks another. A queued clip keeps the provider it was given.",
  },
  {
    route: "speech",
    label: "Speech",
    providerIds: ["omnivoice", "elevenlabs", "google"],
    mediaKinds: ["speech"],
    helpText: "The provider that reads the narration of Film Studio episodes aloud.",
  },
  {
    route: "music",
    label: "Music",
    providerIds: ["ace_step", "elevenlabs", "yue"],
    mediaKinds: ["music"],
    helpText: "The provider that makes the music of Film Studio episodes.",
  },
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

export const MODEL_FIELD_HELP_TEXTS: Record<GenerationMediaKind, string> = {
  image: "The model {name} uses to make a new image.",
  edit_image: "The model {name} uses to change an existing image.",
  video: "The model {name} uses to make a clip.",
  speech: "The model {name} uses to read text aloud.",
  music: "The model {name} uses to make music.",
};

export const ANALYSIS_MEDIA_KIND: MediaKind = "analysis";

export const ADAPTER_PROVIDER_IDS: ReadonlySet<ProviderId> = new Set<ProviderId>(["omnivoice", "ace_step", "yue"]);

export const ADAPTER_BASE_URL_HINT = "Run the adapter of tools/local-servers/ and enter its address.";

export const API_KEY_HELP_TEXT =
  "The key the app sends with every request to {name}. It is stored encrypted and never shown again, only its last 4 characters. Without a key the provider is not set up and its requests fail.";
export const BASE_URL_HELP_TEXT =
  "The address of the local server the app calls, starting with http:// or https://. Without it the provider is not set up and its requests fail.";
export const FLOW_PROJECT_ID_HELP_TEXT =
  "The id in the address of a Flow project you made. Used only when the app cannot create a Flow project for a film project or a film clone.";
export const MAX_CONCURRENT_HELP_TEXT =
  "How many requests to {name} can wait for an answer at once, 1–10. The others wait in the queue.";
export const MIN_INTERVAL_HELP_TEXT =
  "The least time between two requests sent to {name}, 0–600 s, to stay under its rate limit.";
export const GOOGLE_FLOW_MIN_INTERVAL_HELP_SUFFIX = " Google Flow always sends one at a time, at least 3 s apart.";

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
