"use client";

import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { SelectField } from "@/components/molecules/SelectField";
import { labelsToSelectOptions } from "@/features/filmClones/utils";
import {
  FILM_ANALYSIS_INPUT_MODE_HELP_TEXT,
  FILM_ANALYSIS_INPUT_MODE_HINT,
  FILM_ANALYSIS_INPUT_MODE_LABELS,
  FILM_ANALYSIS_SETTINGS_FORM_KEY,
} from "@/features/settings/constants";
import type { FilmAnalysisInputMode } from "@/features/settings/types";
import { buildGoogleAiModelWarning, resolveStepGroupModel } from "@/features/settings/utils";
import { AppSettingsForm } from "./AppSettingsForm";

const FILM_ANALYSIS_INPUT_MODE_OPTIONS = labelsToSelectOptions(FILM_ANALYSIS_INPUT_MODE_LABELS);

interface FilmAnalysisSettingsFormProps {
  onUnsavedChangesChange: (formKey: string, hasUnsavedChanges: boolean) => void;
}

export function FilmAnalysisSettingsForm({ onUnsavedChangesChange }: FilmAnalysisSettingsFormProps) {
  return (
    <AppSettingsForm
      title="Film Analysis"
      formKey={FILM_ANALYSIS_SETTINGS_FORM_KEY}
      onUnsavedChangesChange={onUnsavedChangesChange}
      renderFields={({ shownSettings, isDisabled, onChange }) => {
        const shownInputModes = [shownSettings.filmAnalysisInputMode];
        const audioModel = resolveStepGroupModel(shownSettings, "audio");
        const filmAnalysisModel = resolveStepGroupModel(shownSettings, "filmAnalysis");
        const audioModelWarning = buildGoogleAiModelWarning("audio", audioModel, shownInputModes);
        const filmAnalysisModelWarning = buildGoogleAiModelWarning("filmAnalysis", filmAnalysisModel, shownInputModes);
        return (
          <>
            <SelectField<FilmAnalysisInputMode>
              label="Input mode"
              value={shownSettings.filmAnalysisInputMode}
              options={FILM_ANALYSIS_INPUT_MODE_OPTIONS}
              hint={FILM_ANALYSIS_INPUT_MODE_HINT}
              helpText={FILM_ANALYSIS_INPUT_MODE_HELP_TEXT}
              isDisabled={isDisabled}
              onChange={(filmAnalysisInputMode) => onChange({ filmAnalysisInputMode })}
            />
            {audioModelWarning && <ErrorAlert>{audioModelWarning}</ErrorAlert>}
            {filmAnalysisModelWarning && <ErrorAlert>{filmAnalysisModelWarning}</ErrorAlert>}
          </>
        );
      }}
    />
  );
}
