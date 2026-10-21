import type { PresetChange, PromptKey } from "./types";

export interface PromptSection {
  key: PromptKey;
  title: string;
  usedBy: string;
}

export const PROMPT_SECTIONS: readonly PromptSection[] = [
  { key: "videoToMarkdown", title: "Video → Markdown", usedBy: "Video to Markdown, Film Analysis, Film Clone" },
  { key: "speakersAndSounds", title: "Speakers & sounds", usedBy: "Film Analysis, Film Clone" },
  { key: "characterImage", title: "Character image prompts", usedBy: "Film Analysis" },
  { key: "characterVoice", title: "Character voice prompts", usedBy: "Film Analysis" },
  { key: "scene", title: "Scene prompts", usedBy: "Film Analysis" },
  { key: "filmOutline", title: "Film outline", usedBy: "Film Studio" },
  { key: "filmScript", title: "Film script", usedBy: "Film Studio" },
  { key: "storyBible", title: "Story bible", usedBy: "Film Studio" },
  { key: "cloneAssets", title: "Clone assets", usedBy: "Film Clone" },
  { key: "cloneShots", title: "Clone shots", usedBy: "Film Clone" },
  { key: "cloneLocalization", title: "Clone localization", usedBy: "Film Clone" },
  { key: "cloneScript", title: "Clone script", usedBy: "Film Clone" },
];

export const PROMPT_PRESETS_DESCRIPTION =
  "The prompts the AI model follows in every job. Each job copies the prompts of the preset chosen when it is created.";
export const MAX_PRESET_NAME_LENGTH = 50;
export const MAX_PROMPT_LENGTH = 20_000;
export const PROMPT_SECTION_TITLE_PLACEHOLDER = "{title}";
export const PRESET_NAME_HELP_TEXT = "The name of the preset in every preset list. Default keeps its name.";
export const PROMPT_INSTRUCTIONS_HELP_TEXT =
  "What the AI model is told to do for {title}. A job copies these instructions when it is created, so a change applies to new jobs only. The parts under Added by the app are added by the app and cannot be changed.";
export const PRESET_EXPORT_ACCEPT = ".json,application/json";

export const PRESET_CHANGE_LABELS: Record<PresetChange, string> = {
  created: "Created",
  saved: "Saved",
  restored: "Restored from",
  duplicated: "Duplicated from",
  imported: "Imported from",
};

export const DEFAULT_PRESET_BADGE_LABEL = "Default preset";
export const SYSTEM_PRESET_BADGE_LABEL = "System";
export const CURRENT_VERSION_BADGE_LABEL = "Current";
export const DEFAULT_PROMPT_BADGE_LABEL = "Default";
export const CUSTOMIZED_PROMPT_BADGE_LABEL = "Customized";
export const DEFAULT_PRESET_OPTION_SUFFIX = " (default)";
export const SET_DEFAULT_FIRST_HINT = "Set another preset as default first";
