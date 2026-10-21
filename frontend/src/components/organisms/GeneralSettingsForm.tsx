"use client";

import { SelectField } from "@/components/molecules/SelectField";
import {
  GENERAL_SETTINGS_FORM_KEY,
  SCRIPT_LANGUAGE_HELP_TEXT,
  SCRIPT_LANGUAGE_HINT,
  SCRIPT_LANGUAGE_OPTIONS,
} from "@/features/settings/constants";
import type { ScriptLanguage } from "@/features/settings/types";
import { AppSettingsForm } from "./AppSettingsForm";

interface GeneralSettingsFormProps {
  onUnsavedChangesChange: (formKey: string, hasUnsavedChanges: boolean) => void;
}

export function GeneralSettingsForm({ onUnsavedChangesChange }: GeneralSettingsFormProps) {
  return (
    <AppSettingsForm
      title="General"
      formKey={GENERAL_SETTINGS_FORM_KEY}
      onUnsavedChangesChange={onUnsavedChangesChange}
      renderFields={({ shownSettings, isDisabled, onChange }) => (
        <SelectField<ScriptLanguage>
          label="Script language"
          value={shownSettings.scriptLanguage}
          options={SCRIPT_LANGUAGE_OPTIONS}
          hint={SCRIPT_LANGUAGE_HINT}
          helpText={SCRIPT_LANGUAGE_HELP_TEXT}
          isDisabled={isDisabled}
          onChange={(scriptLanguage) => onChange({ scriptLanguage })}
        />
      )}
    />
  );
}
