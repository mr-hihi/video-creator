import { PROMPT_OVERRIDE_SETTINGS_TAB } from "@/features/settings/constants";
import { buildSettingsPath } from "@/features/settings/utils";
import {
  DEFAULT_PRESET_OPTION_SUFFIX,
  MAX_PRESET_NAME_LENGTH,
  MAX_PROMPT_LENGTH,
  PRESET_CHANGE_LABELS,
  PROMPT_INSTRUCTIONS_HELP_TEXT,
  PROMPT_SECTION_TITLE_PLACEHOLDER,
  PROMPT_SECTIONS,
} from "./constants";
import type { PresetPrompts, PresetSnapshot, PromptKey, PromptPreset, PromptPresetVersion } from "./types";

const MISSING_PRESET_LABEL = "—";
const PROMPT_KEYS: readonly PromptKey[] = PROMPT_SECTIONS.map((section) => section.key);

export function buildPromptPresetsPath(presetId: string): string {
  return `${buildSettingsPath(PROMPT_OVERRIDE_SETTINGS_TAB)}&id=${encodeURIComponent(presetId)}`;
}

export function buildPromptInstructionsHelpText(sectionTitle: string): string {
  return PROMPT_INSTRUCTIONS_HELP_TEXT.replace(PROMPT_SECTION_TITLE_PLACEHOLDER, sectionTitle);
}

export function findDefaultPreset(presets: readonly PromptPreset[]): PromptPreset | undefined {
  return presets.find((preset) => preset.isDefault);
}

export function describePresetOption(preset: PromptPreset): string {
  return preset.isDefault ? `${preset.name}${DEFAULT_PRESET_OPTION_SUFFIX}` : preset.name;
}

export function describePresetSnapshot(preset: PresetSnapshot | undefined): string {
  return preset ? `${preset.name} v${preset.version}` : MISSING_PRESET_LABEL;
}

export function describePresetChange(version: PromptPresetVersion): string {
  const label = PRESET_CHANGE_LABELS[version.change];
  return version.changeSource ? `${label} ${version.changeSource}` : label;
}

export function haveSamePrompts(first: PresetPrompts, second: PresetPrompts): boolean {
  return PROMPT_KEYS.every((key) => first[key] === second[key]);
}

export function isValidPresetName(name: string): boolean {
  const trimmedName = name.trim();
  return trimmedName.length > 0 && trimmedName.length <= MAX_PRESET_NAME_LENGTH;
}

export function areValidPrompts(prompts: PresetPrompts): boolean {
  return PROMPT_KEYS.every((key) => {
    const trimmedPrompt = prompts[key].trim();
    return trimmedPrompt.length > 0 && trimmedPrompt.length <= MAX_PROMPT_LENGTH;
  });
}
