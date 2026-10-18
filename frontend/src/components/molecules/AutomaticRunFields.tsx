import {
  AUTOMATIC_RUN_HINT,
  AUTOMATIC_RUN_LABEL,
  KEEP_ORIGINAL_COUNTRY_VALUE,
  TARGET_COUNTRY_OPTIONS,
  TARGET_SETTING_HINT,
  TARGET_SETTING_LABEL,
  type TargetCountryChoice,
} from "@/features/filmClones/constants";
import type { AutomaticRunChoices, LocalizationChoices } from "@/features/filmClones/types";
import { clearFlagsWithoutCountry } from "@/features/filmClones/utils";
import { CheckboxField } from "./CheckboxField";
import { LocalizationFlagFields } from "./LocalizationFlagFields";
import { SelectField } from "./SelectField";
import { TextAreaField } from "./TextAreaField";

interface AutomaticRunFieldsProps {
  automaticRun: AutomaticRunChoices;
  isDisabled: boolean;
  onChange: (automaticRun: AutomaticRunChoices) => void;
}

export function AutomaticRunFields({ automaticRun, isDisabled, onChange }: AutomaticRunFieldsProps) {
  const { choices } = automaticRun;

  function changeChoices(changes: Partial<LocalizationChoices>) {
    onChange({ ...automaticRun, choices: { ...choices, ...changes } });
  }

  function handleCountryChange(countryChoice: TargetCountryChoice) {
    changeChoices({ targetCountry: countryChoice === KEEP_ORIGINAL_COUNTRY_VALUE ? null : countryChoice });
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <CheckboxField
          label={AUTOMATIC_RUN_LABEL}
          isChecked={automaticRun.shouldRunAutomatically}
          isDisabled={isDisabled}
          onChange={(isTicked) => onChange({ ...automaticRun, shouldRunAutomatically: isTicked })}
        />
        <p className="text-xs text-muted">{AUTOMATIC_RUN_HINT}</p>
      </div>
      {automaticRun.shouldRunAutomatically && (
        <>
          <SelectField<TargetCountryChoice>
            label="Target country"
            value={choices.targetCountry ?? KEEP_ORIGINAL_COUNTRY_VALUE}
            options={TARGET_COUNTRY_OPTIONS}
            isDisabled={isDisabled}
            onChange={handleCountryChange}
          />
          <TextAreaField
            label={TARGET_SETTING_LABEL}
            value={choices.targetSetting}
            hint={TARGET_SETTING_HINT}
            isDisabled={isDisabled}
            onChange={(targetSetting) => changeChoices({ targetSetting })}
          />
          <LocalizationFlagFields
            flags={clearFlagsWithoutCountry(choices)}
            isCountryPicked={choices.targetCountry !== null}
            isDisabled={isDisabled}
            onChange={(flagKey, isTicked) => changeChoices({ [flagKey]: isTicked })}
          />
        </>
      )}
    </div>
  );
}
