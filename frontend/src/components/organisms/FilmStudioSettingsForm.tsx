"use client";

import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { MediaProviderSelectField } from "@/components/molecules/MediaProviderSelectField";
import { IMAGE_ROUTE_PROVIDER_IDS, VIDEO_ROUTE_PROVIDER_IDS } from "@/features/providers/constants";
import { useProviderSettingsQuery } from "@/features/providers/queries";
import {
  FILM_STUDIO_CLIP_PROVIDER_HINT,
  FILM_STUDIO_IMAGE_PROVIDER_HINT,
  FILM_STUDIO_SETTINGS_FORM_KEY,
  ROUTES_BY_MEDIA_PROVIDER_SETTING,
} from "@/features/settings/constants";
import { AppSettingsForm } from "./AppSettingsForm";

interface FilmStudioSettingsFormProps {
  onUnsavedChangesChange: (formKey: string, hasUnsavedChanges: boolean) => void;
}

export function FilmStudioSettingsForm({ onUnsavedChangesChange }: FilmStudioSettingsFormProps) {
  const { data: providerSettings, error } = useProviderSettingsQuery();

  if (!providerSettings) {
    return error ? <ErrorAlert>{error.message}</ErrorAlert> : <PlaceholderMessage>Loading providers…</PlaceholderMessage>;
  }
  return (
    <AppSettingsForm
      title="Film Studio"
      formKey={FILM_STUDIO_SETTINGS_FORM_KEY}
      onUnsavedChangesChange={onUnsavedChangesChange}
      renderFields={({ shownSettings, isDisabled, onChange }) => (
        <>
          <MediaProviderSelectField
            label="Images with"
            hint={FILM_STUDIO_IMAGE_PROVIDER_HINT}
            route={ROUTES_BY_MEDIA_PROVIDER_SETTING.filmStudioImageProvider}
            value={shownSettings.filmStudioImageProvider}
            providerIds={IMAGE_ROUTE_PROVIDER_IDS}
            providerSettings={providerSettings}
            isDisabled={isDisabled}
            onChange={(filmStudioImageProvider) => onChange({ filmStudioImageProvider })}
          />
          <MediaProviderSelectField
            label="Clips with"
            hint={FILM_STUDIO_CLIP_PROVIDER_HINT}
            route={ROUTES_BY_MEDIA_PROVIDER_SETTING.filmStudioClipProvider}
            value={shownSettings.filmStudioClipProvider}
            providerIds={VIDEO_ROUTE_PROVIDER_IDS}
            providerSettings={providerSettings}
            isDisabled={isDisabled}
            onChange={(filmStudioClipProvider) => onChange({ filmStudioClipProvider })}
          />
        </>
      )}
    />
  );
}
