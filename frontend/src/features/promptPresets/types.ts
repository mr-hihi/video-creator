export type PromptKey =
  | "videoToMarkdown"
  | "characterImage"
  | "characterVoice"
  | "scene"
  | "filmScript"
  | "cloneAssets"
  | "cloneShots"
  | "cloneLocalization"
  | "cloneScript";

export type PresetPrompts = Record<PromptKey, string>;

export type PresetChange = "created" | "saved" | "restored" | "duplicated" | "imported";

export interface PromptPreset {
  id: string;
  name: string;
  isSystem: boolean;
  isDefault: boolean;
  currentVersion: number;
  createdAt: string;
  updatedAt: string;
}

export interface PromptPresetDetail extends PromptPreset {
  prompts: PresetPrompts;
}

export interface PromptPresetVersion {
  version: number;
  change: PresetChange;
  changeSource: string | null;
  createdAt: string;
}

export interface PromptPresetVersionDetail extends PromptPresetVersion {
  prompts: PresetPrompts;
}

export interface PromptDefaults {
  prompts: PresetPrompts;
  appAddedParts: PresetPrompts;
}

export interface PresetSnapshot {
  id: string;
  name: string;
  version: number;
}
