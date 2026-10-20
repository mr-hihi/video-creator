"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { Panel } from "@/components/atoms/Panel";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { SuccessNotice } from "@/components/atoms/SuccessNotice";
import { AiModelsFieldset } from "@/components/molecules/AiModelsFieldset";
import { MediaRouteFieldset } from "@/components/molecules/MediaRouteFieldset";
import { ROUTE_FIELDS } from "@/features/providers/constants";
import { useProviderSettingsQuery } from "@/features/providers/queries";
import type { GenerationMediaKind, ProviderId, ProviderSettings, RouteName } from "@/features/providers/types";
import { listAnalysisProviders } from "@/features/providers/utils";
import { AI_MODELS_SETTINGS_FORM_KEY, EMPTY_AI_MODELS_DRAFT, SAVED_NOTICE } from "@/features/settings/constants";
import { useAppSettingsQuery, useUpdateAiModelsMutation } from "@/features/settings/queries";
import type { AiModelSettings, AiModelsDraft, AppSettings } from "@/features/settings/types";
import { buildAiModelsUpdate, hasSettingsChanges, listInUseProviderIds } from "@/features/settings/utils";

type AiModelsDraftChange = (currentDraft: AiModelsDraft) => AiModelsDraft;

interface AiModelsSettingsFormProps {
  onUnsavedChangesChange: (formKey: string, hasUnsavedChanges: boolean) => void;
}

interface AiModelsSettingsFieldsProps extends AiModelsSettingsFormProps {
  settings: AppSettings;
  providerSettings: ProviderSettings;
}

interface AiModelsDraftFieldsProps {
  settings: AppSettings;
  providerSettings: ProviderSettings;
  draft: AiModelsDraft;
  isDisabled: boolean;
  onDraftChange: (draftChange: AiModelsDraftChange) => void;
}

export function AiModelsSettingsForm({ onUnsavedChangesChange }: AiModelsSettingsFormProps) {
  const { data: settings, error: settingsError } = useAppSettingsQuery();
  const { data: providerSettings, error: providersError } = useProviderSettingsQuery();
  const error = settingsError ?? providersError;

  if (!settings || !providerSettings) {
    return error ? <ErrorAlert>{error.message}</ErrorAlert> : <PlaceholderMessage>Loading settings…</PlaceholderMessage>;
  }
  return (
    <Panel title="AI models">
      <div className="flex flex-col gap-4">
        {error && <ErrorAlert>{error.message}</ErrorAlert>}
        <AiModelsSettingsFields
          settings={settings}
          providerSettings={providerSettings}
          onUnsavedChangesChange={onUnsavedChangesChange}
        />
      </div>
    </Panel>
  );
}

function AiModelsSettingsFields({ settings, providerSettings, onUnsavedChangesChange }: AiModelsSettingsFieldsProps) {
  const [draft, setDraft] = useState(EMPTY_AI_MODELS_DRAFT);
  const [notice, setNotice] = useState<string>();
  const saveMutation = useUpdateAiModelsMutation(() => {
    setDraft(EMPTY_AI_MODELS_DRAFT);
    setNotice(SAVED_NOTICE);
  });
  const update = buildAiModelsUpdate(settings, providerSettings, draft);
  const hasUnsavedChanges = hasSettingsChanges(update);

  useEffect(() => {
    onUnsavedChangesChange(AI_MODELS_SETTINGS_FORM_KEY, hasUnsavedChanges);
    return () => onUnsavedChangesChange(AI_MODELS_SETTINGS_FORM_KEY, false);
  }, [hasUnsavedChanges, onUnsavedChangesChange]);

  function changeDraft(draftChange: AiModelsDraftChange) {
    setDraft(draftChange);
    setNotice(undefined);
  }

  return (
    <>
      <AiModelsDraftFields
        settings={settings}
        providerSettings={providerSettings}
        draft={draft}
        isDisabled={saveMutation.isPending}
        onDraftChange={changeDraft}
      />
      <div className="flex flex-wrap items-center gap-2">
        <Button disabled={!hasUnsavedChanges || saveMutation.isPending} onClick={() => saveMutation.mutate(update)}>
          Save
        </Button>
      </div>
      {notice && <SuccessNotice>{notice}</SuccessNotice>}
      {saveMutation.error && <ErrorAlert>{saveMutation.error.message}</ErrorAlert>}
    </>
  );
}

function AiModelsDraftFields({ settings, providerSettings, draft, isDisabled, onDraftChange }: AiModelsDraftFieldsProps) {
  function changeAiModelSettings(changes: Partial<AiModelSettings>) {
    onDraftChange((currentDraft) => ({ ...currentDraft, settings: { ...currentDraft.settings, ...changes } }));
  }

  function changeRoute(route: RouteName, providerId: ProviderId) {
    onDraftChange((currentDraft) => ({ ...currentDraft, routes: { ...currentDraft.routes, [route]: providerId } }));
  }

  function changeModel(providerId: ProviderId, mediaKind: GenerationMediaKind, modelId: string) {
    onDraftChange((currentDraft) => {
      const modelIdsByKind = { ...currentDraft.modelIdsByProvider[providerId], [mediaKind]: modelId };
      return { ...currentDraft, modelIdsByProvider: { ...currentDraft.modelIdsByProvider, [providerId]: modelIdsByKind } };
    });
  }

  return (
    <>
      <AiModelsFieldset
        settings={{ ...settings, ...draft.settings }}
        savedFilmCloneInputMode={settings.filmCloneInputMode}
        analysisProviders={listAnalysisProviders(providerSettings)}
        isDisabled={isDisabled}
        onChange={changeAiModelSettings}
      />
      {ROUTE_FIELDS.map((routeField) => (
        <MediaRouteFieldset
          key={routeField.route}
          routeField={routeField}
          routeProviderId={draft.routes[routeField.route] ?? providerSettings.routes[routeField.route]}
          providers={providerSettings.providers}
          inUseProviderIds={listInUseProviderIds(routeField.route, settings, providerSettings.routes)}
          draftModelIdsByProvider={draft.modelIdsByProvider}
          isDisabled={isDisabled}
          onRouteChange={(providerId) => changeRoute(routeField.route, providerId)}
          onModelChange={changeModel}
        />
      ))}
    </>
  );
}
