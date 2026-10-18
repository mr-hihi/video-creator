"use client";

import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { MediaProviderSelectField } from "@/components/molecules/MediaProviderSelectField";
import { SelectField } from "@/components/molecules/SelectField";
import { labelsToSelectOptions } from "@/features/filmClones/utils";
import { IMAGE_ROUTE_PROVIDER_IDS } from "@/features/providers/constants";
import { useProviderSettingsQuery } from "@/features/providers/queries";
import {
  FILM_CLONE_IMAGE_PROVIDER_HINT,
  FILM_CLONE_SETTINGS_FORM_KEY,
  INPUT_MODE_HINT,
  INPUT_MODE_LABELS,
  ROUTES_BY_MEDIA_PROVIDER_SETTING,
} from "@/features/settings/constants";
import type { InputMode } from "@/features/settings/types";
import { AppSettingsForm } from "./AppSettingsForm";

const INPUT_MODE_OPTIONS = labelsToSelectOptions(INPUT_MODE_LABELS);

interface FilmCloneSettingsFormProps {
  onUnsavedChangesChange: (formKey: string, hasUnsavedChanges: boolean) => void;
}

export function FilmCloneSettingsForm({ onUnsavedChangesChange }: FilmCloneSettingsFormProps) {
  const { data: providerSettings, error } = useProviderSettingsQuery();

  if (!providerSettings) {
    return error ? <ErrorAlert>{error.message}</ErrorAlert> : <PlaceholderMessage>Loading providers…</PlaceholderMessage>;
  }
  return (
    <AppSettingsForm
      title="Film Clone"
      formKey={FILM_CLONE_SETTINGS_FORM_KEY}
      onUnsavedChangesChange={onUnsavedChangesChange}
      renderFields={({ shownSettings, isDisabled, onChange }) => (
        <>
          <MediaProviderSelectField
            label="Images with"
            hint={FILM_CLONE_IMAGE_PROVIDER_HINT}
            route={ROUTES_BY_MEDIA_PROVIDER_SETTING.filmCloneImageProvider}
            value={shownSettings.filmCloneImageProvider}
            providerIds={IMAGE_ROUTE_PROVIDER_IDS}
            providerSettings={providerSettings}
            isDisabled={isDisabled}
            onChange={(filmCloneImageProvider) => onChange({ filmCloneImageProvider })}
          />
          <SelectField<InputMode>
            label="Input mode"
            value={shownSettings.filmCloneInputMode}
            options={INPUT_MODE_OPTIONS}
            hint={INPUT_MODE_HINT}
            isDisabled={isDisabled}
            onChange={(filmCloneInputMode) => onChange({ filmCloneInputMode })}
          />
        </>
      )}
    />
  );
}
