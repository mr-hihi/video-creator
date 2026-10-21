import type { RouteName } from "@/features/providers/types";
import type {
  AiModelsDraft,
  AiProviderId,
  AiStepGroup,
  AiStepModels,
  FilmAnalysisInputMode,
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
  { value: "film-analysis", label: "Film Analysis" },
  { value: "film-clone", label: "Film Clone" },
  { value: "film-studio", label: "Film Studio" },
] as const;

export type SettingsTab = (typeof SETTINGS_TAB_OPTIONS)[number]["value"];

export const GENERAL_SETTINGS_TAB: SettingsTab = "general";
export const AI_MODELS_SETTINGS_TAB: SettingsTab = "ai-models";
export const PROMPT_OVERRIDE_SETTINGS_TAB: SettingsTab = "prompt-override";
export const FILM_ANALYSIS_SETTINGS_TAB: SettingsTab = "film-analysis";
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

export const SCRIPT_LANGUAGE_HINT = "The language Film Clone writes scripts in.";
export const SCRIPT_LANGUAGE_HELP_TEXT =
  "Film Clone writes the script of a clone in this language. Follow the target country: the language of the country picked in Localization, or the film's own language when no country is picked. A clone keeps the language it had when its localization was chosen. Film Studio narrates only Vietnamese, English or Japanese.";

export const DEFAULT_INPUT_MODE: InputMode = "subtitles";
export const FULL_VIDEO_INPUT_MODE: FilmAnalysisInputMode = "full_video";

export const AI_PROVIDER_IDS: readonly AiProviderId[] = ["claude_cli", "google", "openai"];

export const GOOGLE_AI_PROVIDER_ID: AiProviderId = "google";

export const AI_STEP_GROUPS: readonly AiStepGroup[] = ["moments", "audio", "filmAnalysis", "filmScript", "filmClone"];

export const AI_STEP_GROUP_LABELS: Record<AiStepGroup, string> = {
  moments: "Key moments",
  audio: "Audio",
  filmAnalysis: "Film analysis",
  filmScript: "Film script",
  filmClone: "Film clone",
};

export const AI_STEP_GROUP_HINTS: Record<AiStepGroup, string> = {
  moments: "Picks the key moments of every video.",
  audio: "Hears the speakers and sounds in Frame image + audio mode. Google AI only.",
  filmAnalysis: "Writes the character image, voice and scene prompts. Google AI only in Full video mode.",
  filmScript: "Writes the scripts of Film Studio episodes.",
  filmClone: "Finds assets and shots, proposes changes and writes Film Clone scripts.",
};

export const AI_STEP_GROUP_HELP_TEXTS: Record<AiStepGroup, string> = {
  moments:
    "Picks the moments that get a frame, from the transcript — and from one frame per second in Whole video or Frame image + audio mode. Used by Video to Markdown, Film Analysis and Film Clone.",
  audio:
    "Listens to the film's audio in Frame image + audio mode of Film Analysis and Film Clone: tells the speakers apart by voice and marks actions, silences, ambient sounds and music, which add frames. Must be a Google AI model.",
  filmAnalysis:
    "Writes the character image, character voice and scene prompts of Film Analysis. In Full video mode it watches the compressed film itself, so it must be a Google AI model.",
  filmScript: "Writes the outline, the part scripts and the story bible of Film Studio episodes.",
  filmClone:
    "Finds the assets and shots of a film, proposes the localized changes and writes the Film Clone script.",
};

export const AI_STEP_GROUPS_BY_RUN = {
  videoToMarkdown: ["moments"],
  filmAnalysisRerun: ["filmAnalysis"],
  filmScript: ["filmScript"],
} as const satisfies Record<string, readonly AiStepGroup[]>;

export const FILM_ANALYSIS_AI_STEP_GROUPS_BY_INPUT_MODE: Record<FilmAnalysisInputMode, readonly AiStepGroup[]> = {
  subtitles: ["moments", "filmAnalysis"],
  whole_video: ["moments", "audio", "filmAnalysis"],
  full_video: ["filmAnalysis"],
};

export const FILM_CLONE_AI_STEP_GROUPS_BY_INPUT_MODE: Record<InputMode, readonly AiStepGroup[]> = {
  subtitles: ["moments", "filmClone"],
  whole_video: ["moments", "audio", "filmClone"],
};

export const GOOGLE_AI_INPUT_MODE_BY_STEP_GROUP: Partial<Record<AiStepGroup, FilmAnalysisInputMode>> = {
  audio: "whole_video",
  filmAnalysis: "full_video",
};

export const SAME_AS_ALL_STEPS_STEP_MODELS: AiStepModels = {
  moments: null,
  audio: null,
  filmAnalysis: null,
  filmScript: null,
  filmClone: null,
};

export const SAME_AS_ALL_STEPS_OPTION_VALUE = "same";
export const AI_MODEL_OPTION_VALUE_SEPARATOR = ":";
export const AI_MODEL_LIST_SEPARATOR = " · ";
export const EMPTY_AI_USED_LABEL = "—";
export const EMPTY_INPUT_MODE_LABEL = "—";

export const VIDEO_TO_MARKDOWN_INPUT_MODE_LABELS: Record<InputMode, string> = {
  subtitles: "Subtitles",
  whole_video: "Whole video",
};

export const FILM_CLONE_INPUT_MODE_LABELS: Record<InputMode, string> = {
  subtitles: "Subtitles",
  whole_video: "Frame image + audio",
};

export const FILM_ANALYSIS_INPUT_MODE_LABELS: Record<FilmAnalysisInputMode, string> = {
  ...FILM_CLONE_INPUT_MODE_LABELS,
  full_video: "Full video",
};

export const ALL_STEPS_MODEL_HINT = "The model of every step set to Same as all steps.";
export const ALL_STEPS_MODEL_HELP_TEXT =
  "Every step whose row below is Same as all steps uses this model. Claude CLI runs the signed-in claude command; Google AI and OpenAI need their key in General.";

export const VIDEO_TO_MARKDOWN_INPUT_MODE_HINT = "What the model sees to pick key moments.";
export const VIDEO_TO_MARKDOWN_INPUT_MODE_HELP_TEXT =
  "Subtitles: the model reads only the transcript — the fastest. Whole video: it also sees one frame per second, so it can pick moments without speech — slower, with more calls on long videos.";

export const FILM_ANALYSIS_INPUT_MODE_HINT = "What the model gets from the film.";
export const FILM_ANALYSIS_INPUT_MODE_HELP_TEXT =
  "Subtitles: the model reads the transcript to pick key moments, then writes the prompts from their frames. Frame image + audio: it also sees one frame per second, and Gemini hears who speaks and the sounds, which add frames — slower, and Audio needs a Google AI model. Full video: Gemini watches the whole film, compressed to 480 px and 24 fps, and writes the prompts at once — no frames or video notes, and Film analysis needs a Google AI model.";

export const FILM_CLONE_INPUT_MODE_HINT = "What the model gets from the film.";
export const FILM_CLONE_INPUT_MODE_HELP_TEXT =
  "Subtitles: the model reads the transcript to pick key moments. Frame image + audio: it also sees one frame per second, and Gemini hears who speaks and the sounds, which add sound shots — slower, with more calls on long videos, and Audio needs a Google AI model.";

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

export const FILM_CLONE_IMAGE_PROVIDER_HELP_TEXT =
  "The provider of the asset reference images and scene images of Film Clone. Same as AI models follows the Images route of the AI models tab; another choice applies to Film Clone only. A queued image keeps the provider it was given.";
export const FILM_STUDIO_IMAGE_PROVIDER_HELP_TEXT =
  "The provider of the reference images and scene images of Film Studio. Same as AI models follows the Images route of the AI models tab; another choice applies to Film Studio only. A queued image keeps the provider it was given.";
export const FILM_STUDIO_CLIP_PROVIDER_HELP_TEXT =
  "The provider of the scene clips of Film Studio. Same as AI models follows the Clips route of the AI models tab; another choice applies to Film Studio only. A queued clip keeps the provider it was given.";

export const MEDIA_PROVIDER_SEPARATOR = " · ";

export const SAVED_NOTICE = "Saved";

export const EMPTY_AI_MODELS_DRAFT: AiModelsDraft = { settings: {}, routes: {}, modelIdsByProvider: {} };

export const GENERAL_SETTINGS_FORM_KEY = "general";
export const AI_MODELS_SETTINGS_FORM_KEY = "aiModels";
export const FILM_ANALYSIS_SETTINGS_FORM_KEY = "filmAnalysis";
export const FILM_CLONE_SETTINGS_FORM_KEY = "filmClone";
export const FILM_STUDIO_SETTINGS_FORM_KEY = "filmStudio";
export const PROMPT_PRESETS_FORM_KEY = "promptPresets";
