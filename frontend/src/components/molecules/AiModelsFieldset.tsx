import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import type { SelectOption } from "@/components/atoms/Select";
import { labelsToSelectOptions } from "@/features/filmClones/utils";
import type { Provider } from "@/features/providers/types";
import {
  AI_STEP_GROUP_HINTS,
  AI_STEP_GROUP_LABELS,
  AI_STEP_GROUPS,
  ALL_STEPS_MODEL_HINT,
  FILM_ANALYSIS_INPUT_MODE_HINT,
  FILM_ANALYSIS_INPUT_MODE_LABELS,
  SAME_AS_ALL_STEPS_OPTION_VALUE,
  SAME_AS_ALL_STEPS_STEP_MODELS,
  VIDEO_TO_MARKDOWN_INPUT_MODE_HINT,
  VIDEO_TO_MARKDOWN_INPUT_MODE_LABELS,
} from "@/features/settings/constants";
import type {
  AiModel,
  AiModelSettings,
  AiStepGroup,
  FilmAnalysisInputMode,
  InputMode,
} from "@/features/settings/types";
import {
  aiModelToOptionValue,
  buildAiModelOptions,
  buildGoogleAiModelWarning,
  describeSameAsAllStepsOption,
  hasOnlySameAsAllStepsModels,
  resolveAiModel,
  resolveStepGroupModel,
} from "@/features/settings/utils";
import { ProviderNotSetUpAlert } from "./ProviderNotSetUpAlert";
import { SelectField } from "./SelectField";

const VIDEO_TO_MARKDOWN_INPUT_MODE_OPTIONS = labelsToSelectOptions(VIDEO_TO_MARKDOWN_INPUT_MODE_LABELS);
const FILM_ANALYSIS_INPUT_MODE_OPTIONS = labelsToSelectOptions(FILM_ANALYSIS_INPUT_MODE_LABELS);

interface AiModelsFieldsetProps {
  settings: AiModelSettings;
  savedFilmCloneInputMode: InputMode;
  analysisProviders: readonly Provider[];
  isDisabled: boolean;
  onChange: (changes: Partial<AiModelSettings>) => void;
}

interface AiStepModelFieldProps {
  group: AiStepGroup;
  stepModel: AiModel | null;
  googleAiWarning: string | undefined;
  options: readonly SelectOption<string>[];
  analysisProviders: readonly Provider[];
  isDisabled: boolean;
  onChange: (optionValue: string) => void;
}

export function AiModelsFieldset({
  settings,
  savedFilmCloneInputMode,
  analysisProviders,
  isDisabled,
  onChange,
}: AiModelsFieldsetProps) {
  const modelOptions = buildAiModelOptions(analysisProviders);
  const allStepsModel = resolveAiModel(settings.aiModel, analysisProviders);
  const shownInputModes = [settings.filmAnalysisInputMode, savedFilmCloneInputMode];
  const stepModelOptions = [
    { value: SAME_AS_ALL_STEPS_OPTION_VALUE, label: describeSameAsAllStepsOption(allStepsModel.label) },
    ...modelOptions,
  ];

  function findOptionModel(optionValue: string): AiModel | undefined {
    return modelOptions.find((option) => option.value === optionValue)?.aiModel;
  }

  function changeAllStepsModel(optionValue: string) {
    const selectedModel = findOptionModel(optionValue);
    if (selectedModel) onChange({ aiModel: selectedModel });
  }

  function changeStepModel(group: AiStepGroup, optionValue: string) {
    onChange({ aiStepModels: { ...settings.aiStepModels, [group]: findOptionModel(optionValue) ?? null } });
  }

  return (
    <fieldset className="flex min-w-0 flex-col gap-4 rounded-lg border border-border p-4">
      <legend className="px-1 text-sm font-semibold">Text</legend>
      <div className="flex flex-col gap-2">
        <SelectField
          label="All steps"
          value={aiModelToOptionValue(settings.aiModel)}
          options={modelOptions}
          hint={ALL_STEPS_MODEL_HINT}
          isDisabled={isDisabled}
          action={
            <Button
              variant="secondary"
              disabled={isDisabled || hasOnlySameAsAllStepsModels(settings.aiStepModels)}
              onClick={() => onChange({ aiStepModels: SAME_AS_ALL_STEPS_STEP_MODELS })}
            >
              Apply to all steps
            </Button>
          }
          onChange={changeAllStepsModel}
        />
        {!allStepsModel.isSetUp && (
          <ProviderNotSetUpAlert providerId={settings.aiModel.provider} providerName={allStepsModel.providerName} />
        )}
      </div>
      {AI_STEP_GROUPS.map((group) => (
        <AiStepModelField
          key={group}
          group={group}
          stepModel={settings.aiStepModels[group]}
          googleAiWarning={buildGoogleAiModelWarning(group, resolveStepGroupModel(settings, group), shownInputModes)}
          options={stepModelOptions}
          analysisProviders={analysisProviders}
          isDisabled={isDisabled}
          onChange={(optionValue) => changeStepModel(group, optionValue)}
        />
      ))}
      <SelectField<InputMode>
        label="Video to Markdown input"
        value={settings.inputMode}
        options={VIDEO_TO_MARKDOWN_INPUT_MODE_OPTIONS}
        hint={VIDEO_TO_MARKDOWN_INPUT_MODE_HINT}
        isDisabled={isDisabled}
        onChange={(inputMode) => onChange({ inputMode })}
      />
      <SelectField<FilmAnalysisInputMode>
        label="Film Analysis input"
        value={settings.filmAnalysisInputMode}
        options={FILM_ANALYSIS_INPUT_MODE_OPTIONS}
        hint={FILM_ANALYSIS_INPUT_MODE_HINT}
        isDisabled={isDisabled}
        onChange={(filmAnalysisInputMode) => onChange({ filmAnalysisInputMode })}
      />
    </fieldset>
  );
}

function AiStepModelField({
  group,
  stepModel,
  googleAiWarning,
  options,
  analysisProviders,
  isDisabled,
  onChange,
}: AiStepModelFieldProps) {
  const resolvedStepModel = stepModel && resolveAiModel(stepModel, analysisProviders);

  return (
    <div className="flex flex-col gap-2">
      <SelectField
        label={AI_STEP_GROUP_LABELS[group]}
        value={stepModel ? aiModelToOptionValue(stepModel) : SAME_AS_ALL_STEPS_OPTION_VALUE}
        options={options}
        hint={AI_STEP_GROUP_HINTS[group]}
        isDisabled={isDisabled}
        onChange={onChange}
      />
      {stepModel && resolvedStepModel && !resolvedStepModel.isSetUp && (
        <ProviderNotSetUpAlert providerId={stepModel.provider} providerName={resolvedStepModel.providerName} />
      )}
      {googleAiWarning && <ErrorAlert>{googleAiWarning}</ErrorAlert>}
    </div>
  );
}
