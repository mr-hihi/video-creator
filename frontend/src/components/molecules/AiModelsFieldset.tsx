import { Button } from "@/components/atoms/Button";
import type { SelectOption } from "@/components/atoms/Select";
import { labelsToSelectOptions } from "@/features/filmClones/utils";
import type { Provider } from "@/features/providers/types";
import {
  AI_MODELS_INPUT_MODE_HINT,
  AI_STEP_GROUP_HINTS,
  AI_STEP_GROUP_LABELS,
  AI_STEP_GROUPS,
  ALL_STEPS_MODEL_HINT,
  INPUT_MODE_LABELS,
  SAME_AS_ALL_STEPS_OPTION_VALUE,
  SAME_AS_ALL_STEPS_STEP_MODELS,
} from "@/features/settings/constants";
import type { AiModel, AiModelSettings, AiStepGroup, InputMode } from "@/features/settings/types";
import {
  aiModelToOptionValue,
  buildAiModelOptions,
  describeSameAsAllStepsOption,
  hasOnlySameAsAllStepsModels,
  resolveAiModel,
} from "@/features/settings/utils";
import { ProviderNotSetUpAlert } from "./ProviderNotSetUpAlert";
import { SelectField } from "./SelectField";

const INPUT_MODE_OPTIONS = labelsToSelectOptions(INPUT_MODE_LABELS);

interface AiModelsFieldsetProps {
  settings: AiModelSettings;
  analysisProviders: readonly Provider[];
  isDisabled: boolean;
  onChange: (changes: Partial<AiModelSettings>) => void;
}

interface AiStepModelFieldProps {
  group: AiStepGroup;
  stepModel: AiModel | null;
  options: readonly SelectOption<string>[];
  analysisProviders: readonly Provider[];
  isDisabled: boolean;
  onChange: (optionValue: string) => void;
}

export function AiModelsFieldset({ settings, analysisProviders, isDisabled, onChange }: AiModelsFieldsetProps) {
  const modelOptions = buildAiModelOptions(analysisProviders);
  const allStepsModel = resolveAiModel(settings.aiModel, analysisProviders);
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
          options={stepModelOptions}
          analysisProviders={analysisProviders}
          isDisabled={isDisabled}
          onChange={(optionValue) => changeStepModel(group, optionValue)}
        />
      ))}
      <SelectField<InputMode>
        label="Input mode"
        value={settings.inputMode}
        options={INPUT_MODE_OPTIONS}
        hint={AI_MODELS_INPUT_MODE_HINT}
        isDisabled={isDisabled}
        onChange={(inputMode) => onChange({ inputMode })}
      />
    </fieldset>
  );
}

function AiStepModelField({ group, stepModel, options, analysisProviders, isDisabled, onChange }: AiStepModelFieldProps) {
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
    </div>
  );
}
