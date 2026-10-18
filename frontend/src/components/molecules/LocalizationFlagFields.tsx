import { LOCALIZATION_FLAGS, PICK_COUNTRY_HINT } from "@/features/filmClones/constants";
import type { LocalizationFlagKey, LocalizationFlags } from "@/features/filmClones/types";
import { CheckboxField } from "./CheckboxField";

interface LocalizationFlagFieldsProps {
  flags: LocalizationFlags;
  isCountryPicked: boolean;
  isDisabled: boolean;
  onChange?: (flagKey: LocalizationFlagKey, isTicked: boolean) => void;
}

export function LocalizationFlagFields({ flags, isCountryPicked, isDisabled, onChange }: LocalizationFlagFieldsProps) {
  return (
    <div role="group" aria-label="What to change" className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-x-6 gap-y-2">
        {LOCALIZATION_FLAGS.map((flag) => (
          <CheckboxField
            key={flag.key}
            label={flag.label}
            isChecked={flags[flag.key]}
            isDisabled={!isCountryPicked || isDisabled}
            onChange={(isTicked) => onChange?.(flag.key, isTicked)}
          />
        ))}
      </div>
      {!isCountryPicked && <p className="text-xs text-muted">{PICK_COUNTRY_HINT}</p>}
    </div>
  );
}
