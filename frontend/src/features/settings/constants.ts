import type { RouteName } from "@/features/providers/types";
import type {
  AiModelsDraft,
  AiProviderId,
  AiStepGroup,
  AiStepModels,
  InputMode,
  MediaProviderSettingKey,
  ScriptLanguage,
} from "./types";

export interface ScriptLanguageOption {
  value: ScriptLanguage;
  label: string;
}

export const SETTINGS_PATH = "/settings";

export const SETTINGS_TAB_OPTIONS = [
  { value: "general", label: "General" },
  { value: "ai-models", label: "AI models" },
  { value: "prompt-override", label: "Prompt override" },
  { value: "film-clone", label: "Film Clone" },
  { value: "film-studio", label: "Film Studio" },
] as const;

export type SettingsTab = (typeof SETTINGS_TAB_OPTIONS)[number]["value"];

export const GENERAL_SETTINGS_TAB: SettingsTab = "general";
export const AI_MODELS_SETTINGS_TAB: SettingsTab = "ai-models";
export const PROMPT_OVERRIDE_SETTINGS_TAB: SettingsTab = "prompt-override";
export const FILM_CLONE_SETTINGS_TAB: SettingsTab = "film-clone";
export const FILM_STUDIO_SETTINGS_TAB: SettingsTab = "film-studio";
export const DEFAULT_SETTINGS_TAB: SettingsTab = GENERAL_SETTINGS_TAB;

export const SCRIPT_LANGUAGE_OPTIONS: readonly ScriptLanguageOption[] = [
  { value: "follow_target_country", label: "Follow the target country" },
  { value: "vi", label: "Vietnamese" },
  { value: "ja", label: "Japanese" },
  { value: "ko", label: "Korean" },
  { value: "zh", label: "Chinese" },
  { value: "en", label: "English" },
  { value: "fr", label: "French" },
  { value: "th", label: "Thai" },
  { value: "hi", label: "Hindi" },
  { value: "id", label: "Indonesian" },
];

export const SCRIPT_LANGUAGE_HINT =
  "The language Film Clone writes scripts in. Film Studio narrates only Vietnamese, English or Japanese.";

export const DEFAULT_INPUT_MODE: InputMode = "subtitles";

export const AI_PROVIDER_IDS: readonly AiProviderId[] = ["claude_cli", "google", "openai"];

export const AI_STEP_GROUPS: readonly AiStepGroup[] = ["moments", "filmAnalysis", "filmScript", "filmClone"];

export const AI_STEP_GROUP_LABELS: Record<AiStepGroup, string> = {
  moments: "Key moments",
  filmAnalysis: "Film analysis",
  filmScript: "Film script",
  filmClone: "Film clone",
};

export const AI_STEP_GROUP_HINTS: Record<AiStepGroup, string> = {
  moments: "Picks the key moments of every video.",
  filmAnalysis: "Writes the character image, voice and scene prompts.",
  filmScript: "Writes the scripts of Film Studio episodes.",
  filmClone: "Finds assets and shots, proposes changes and writes Film Clone scripts.",
};

export const AI_STEP_GROUPS_BY_RUN = {
  videoToMarkdown: ["moments"],
  filmAnalysis: ["moments", "filmAnalysis"],
  filmAnalysisRerun: ["filmAnalysis"],
  filmClone: ["moments", "filmClone"],
  filmScript: ["filmScript"],
} as const satisfies Record<string, readonly AiStepGroup[]>;

export const SAME_AS_ALL_STEPS_STEP_MODELS: AiStepModels = {
  moments: null,
  filmAnalysis: null,
  filmScript: null,
  filmClone: null,
};

export const SAME_AS_ALL_STEPS_OPTION_VALUE = "same";
export const AI_MODEL_OPTION_VALUE_SEPARATOR = ":";
export const AI_MODEL_LIST_SEPARATOR = " · ";
export const EMPTY_AI_USED_LABEL = "—";

export const INPUT_MODE_LABELS: Record<InputMode, string> = {
  subtitles: "Subtitles",
  whole_video: "Whole video",
};

export const ALL_STEPS_MODEL_HINT = "The model of every step set to Same as all steps.";

export const INPUT_MODE_HINT =
  "Subtitles: the model reads the transcript to pick key moments. Whole video: it also sees one frame per second — slower, with more calls on long videos.";

export const AI_MODELS_INPUT_MODE_HINT = `For Video to Markdown and Film Analysis. ${INPUT_MODE_HINT}`;

export const ROUTES_BY_MEDIA_PROVIDER_SETTING: Record<MediaProviderSettingKey, RouteName> = {
  filmCloneImageProvider: "image",
  filmStudioImageProvider: "image",
  filmStudioClipProvider: "video",
};

export const MEDIA_PROVIDER_SETTING_KEYS = Object.keys(ROUTES_BY_MEDIA_PROVIDER_SETTING) as MediaProviderSettingKey[];

export const SAME_AS_AI_MODELS_OPTION_VALUE = "same";

export const FILM_CLONE_IMAGE_PROVIDER_HINT = "Makes the asset references and scene images of Film Clone.";
export const FILM_STUDIO_IMAGE_PROVIDER_HINT = "Makes the reference and scene images of Film Studio.";
export const FILM_STUDIO_CLIP_PROVIDER_HINT = "Makes the clips of Film Studio.";

export const MEDIA_PROVIDER_SEPARATOR = " · ";

export const SAVED_NOTICE = "Saved";

export const EMPTY_AI_MODELS_DRAFT: AiModelsDraft = { settings: {}, routes: {}, modelIdsByProvider: {} };

export const GENERAL_SETTINGS_FORM_KEY = "general";
export const AI_MODELS_SETTINGS_FORM_KEY = "aiModels";
export const FILM_CLONE_SETTINGS_FORM_KEY = "filmClone";
export const FILM_STUDIO_SETTINGS_FORM_KEY = "filmStudio";
export const PROMPT_PRESETS_FORM_KEY = "promptPresets";
