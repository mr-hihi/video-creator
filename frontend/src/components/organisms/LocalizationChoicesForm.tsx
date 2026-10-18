"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { LocalizationFlagFields } from "@/components/molecules/LocalizationFlagFields";
import { SelectField } from "@/components/molecules/SelectField";
import { TextAreaField } from "@/components/molecules/TextAreaField";
import {
  KEEP_ORIGINAL_COUNTRY_VALUE,
  TARGET_COUNTRY_OPTIONS,
  TARGET_SETTING_HINT,
  TARGET_SETTING_LABEL,
  UNTICKED_LOCALIZATION_FLAGS,
  type TargetCountryChoice,
} from "@/features/filmClones/constants";
import { useLocalizeFilmCloneMutation } from "@/features/filmClones/queries";
import type {
  FilmCloneDetail,
  LocalizationChoices,
  LocalizationFlagKey,
  LocalizationFlags,
} from "@/features/filmClones/types";
import { hasTickedLocalizationFlag } from "@/features/filmClones/utils";
import { FilmCloneMediaLine } from "./FilmCloneMediaLine";
import { ScriptLanguagePreview } from "./ScriptLanguagePreview";

interface LocalizationChoicesFormProps {
  clone: FilmCloneDetail;
}

export function LocalizationChoicesForm({ clone }: LocalizationChoicesFormProps) {
  const localizeMutation = useLocalizeFilmCloneMutation();
  const [countryChoice, setCountryChoice] = useState<TargetCountryChoice>(
    clone.targetCountry ?? KEEP_ORIGINAL_COUNTRY_VALUE,
  );
  const [targetSetting, setTargetSetting] = useState(clone.targetSetting ?? "");
  const [tickedFlags, setTickedFlags] = useState<LocalizationFlags>(() => ({
    changeAppearance: clone.changeAppearance,
    changeCostume: clone.changeCostume,
    changeSetting: clone.changeSetting,
  }));

  const isLocalizing = localizeMutation.isPending;
  const targetCountry = countryChoice === KEEP_ORIGINAL_COUNTRY_VALUE ? null : countryChoice;
  const choices: LocalizationChoices = {
    targetCountry,
    targetSetting,
    ...(targetCountry ? tickedFlags : UNTICKED_LOCALIZATION_FLAGS),
  };

  function handleFlagChange(flagKey: LocalizationFlagKey, isTicked: boolean) {
    setTickedFlags((currentFlags) => ({ ...currentFlags, [flagKey]: isTicked }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    localizeMutation.mutate({ cloneId: clone.id, choices });
  }

  return (
    <form onSubmit={handleSubmit} className="flex max-w-xl flex-col gap-5">
      <SelectField<TargetCountryChoice>
        label="Target country"
        value={countryChoice}
        options={TARGET_COUNTRY_OPTIONS}
        isDisabled={isLocalizing}
        onChange={setCountryChoice}
      />
      <TextAreaField
        label={TARGET_SETTING_LABEL}
        value={targetSetting}
        hint={TARGET_SETTING_HINT}
        isDisabled={isLocalizing}
        onChange={setTargetSetting}
      />
      <LocalizationFlagFields
        flags={choices}
        isCountryPicked={targetCountry !== null}
        isDisabled={isLocalizing}
        onChange={handleFlagChange}
      />
      <ScriptLanguagePreview targetCountry={targetCountry} videoNotes={clone.videoNotes} />
      <FilmCloneMediaLine />
      {localizeMutation.isError && <ErrorAlert>{localizeMutation.error.message}</ErrorAlert>}
      <div className="self-start">
        <Button type="submit" disabled={isLocalizing}>
          {hasTickedLocalizationFlag(choices) ? "Localize" : "Write script"}
        </Button>
      </div>
    </form>
  );
}
