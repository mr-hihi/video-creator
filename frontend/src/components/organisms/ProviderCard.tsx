"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { SuccessNotice } from "@/components/atoms/SuccessNotice";
import { ApiKeyField } from "@/components/molecules/ApiKeyField";
import { ConnectionTestResult } from "@/components/molecules/ConnectionTestResult";
import { ProviderCardHeader } from "@/components/molecules/ProviderCardHeader";
import { ProviderModelsLine } from "@/components/molecules/ProviderModelsLine";
import { ProviderPacingFields } from "@/components/molecules/ProviderPacingFields";
import { TextField } from "@/components/molecules/TextField";
import {
  ADAPTER_BASE_URL_HINT,
  ADAPTER_PROVIDER_IDS,
  API_KEY_HELP_TEXT,
  BASE_URL_HELP_TEXT,
  EMPTY_PROVIDER_DRAFT,
  FLOW_PROJECT_ID_HELP_TEXT,
  MAX_CONCURRENT_HELP_TEXT,
} from "@/features/providers/constants";
import { useTestProviderConnectionMutation, useUpdateProviderMutation } from "@/features/providers/queries";
import type { Provider, ProviderDraft } from "@/features/providers/types";
import {
  buildApiKeyPlaceholder,
  buildMinIntervalHelpText,
  buildProviderHelpText,
  buildProviderUpdate,
  computeRemainingPauseSeconds,
  hasProviderChanges,
  hasValidPacing,
} from "@/features/providers/utils";
import { SAVED_NOTICE } from "@/features/settings/constants";
import { GoogleFlowActions } from "./GoogleFlowActions";

interface ProviderCardProps {
  provider: Provider;
  isSecretKeySet: boolean;
  referenceTimeMs: number;
  onUnsavedChangesChange: (formKey: string, hasUnsavedChanges: boolean) => void;
}

interface ProviderDraftFieldsProps {
  provider: Provider;
  draft: ProviderDraft;
  isSecretKeySet: boolean;
  isSaving: boolean;
  isRemoveKeyDisabled: boolean;
  remainingPauseSeconds: number;
  onDraftChange: (draftChange: Partial<ProviderDraft>) => void;
  onRemoveKey: () => void;
}

export function ProviderCard({ provider, isSecretKeySet, referenceTimeMs, onUnsavedChangesChange }: ProviderCardProps) {
  const [draft, setDraft] = useState<ProviderDraft>(EMPTY_PROVIDER_DRAFT);
  const [notice, setNotice] = useState<string>();
  const saveMutation = useUpdateProviderMutation(() => {
    setDraft(EMPTY_PROVIDER_DRAFT);
    setNotice(SAVED_NOTICE);
  });
  const removeKeyMutation = useUpdateProviderMutation(() => setDraft((currentDraft) => ({ ...currentDraft, apiKey: "" })));
  const testMutation = useTestProviderConnectionMutation();
  const cardMutations = [saveMutation, removeKeyMutation, testMutation];
  const isBusy = cardMutations.some((mutation) => mutation.isPending);
  const failedMutation = cardMutations.find((mutation) => mutation.isError);
  const update = buildProviderUpdate(provider, draft);
  const hasUnsavedChanges = hasProviderChanges(update);
  const canSave = hasUnsavedChanges && hasValidPacing(draft) && !isBusy;

  useEffect(() => {
    onUnsavedChangesChange(provider.id, hasUnsavedChanges);
    return () => onUnsavedChangesChange(provider.id, false);
  }, [provider.id, hasUnsavedChanges, onUnsavedChangesChange]);

  function changeDraft(draftChange: Partial<ProviderDraft>) {
    setDraft((currentDraft) => ({ ...currentDraft, ...draftChange }));
    setNotice(undefined);
  }

  function removeKey() {
    if (!window.confirm(`Remove the API key of ${provider.name}?`)) return;
    setNotice(undefined);
    removeKeyMutation.mutate({ providerId: provider.id, update: { apiKey: null } });
  }

  const remainingPauseSeconds = computeRemainingPauseSeconds(provider.pausedUntil, referenceTimeMs);
  return (
    <article className="flex min-w-0 flex-col gap-4 rounded-lg border border-border p-4">
      <ProviderCardHeader provider={provider} remainingPauseSeconds={remainingPauseSeconds} />
      <ProviderDraftFields
        provider={provider}
        draft={draft}
        isSecretKeySet={isSecretKeySet}
        isSaving={saveMutation.isPending || removeKeyMutation.isPending}
        isRemoveKeyDisabled={isBusy}
        remainingPauseSeconds={remainingPauseSeconds}
        onDraftChange={changeDraft}
        onRemoveKey={removeKey}
      />
      <div className="flex flex-wrap items-center gap-2">
        {provider.kind !== "cli" && (
          <Button disabled={!canSave} onClick={() => saveMutation.mutate({ providerId: provider.id, update })}>
            Save
          </Button>
        )}
        <Button variant="secondary" disabled={isBusy} onClick={() => testMutation.mutate(provider.id)}>
          Test connection
        </Button>
      </div>
      {notice && <SuccessNotice>{notice}</SuccessNotice>}
      {provider.lastTest && <ConnectionTestResult connectionTest={provider.lastTest} />}
      {failedMutation?.error && <ErrorAlert>{failedMutation.error.message}</ErrorAlert>}
    </article>
  );
}

function ProviderDraftFields({
  provider,
  draft,
  isSecretKeySet,
  isSaving,
  isRemoveKeyDisabled,
  remainingPauseSeconds,
  onDraftChange,
  onRemoveKey,
}: ProviderDraftFieldsProps) {
  return (
    <>
      {provider.kind === "api" && (
        <ApiKeyField
          value={draft.apiKey}
          placeholder={buildApiKeyPlaceholder(provider)}
          helpText={buildProviderHelpText(API_KEY_HELP_TEXT, provider.name)}
          hasStoredKey={provider.hasKey}
          isDisabled={!isSecretKeySet || isSaving}
          isRemoveDisabled={isRemoveKeyDisabled}
          onChange={(apiKey) => onDraftChange({ apiKey })}
          onRemove={onRemoveKey}
        />
      )}
      {provider.kind === "local" && (
        <TextField
          label="Base URL"
          value={draft.baseUrl ?? provider.baseUrl ?? ""}
          hint={ADAPTER_PROVIDER_IDS.has(provider.id) ? ADAPTER_BASE_URL_HINT : undefined}
          helpText={BASE_URL_HELP_TEXT}
          isDisabled={isSaving}
          onChange={(baseUrl) => onDraftChange({ baseUrl })}
        />
      )}
      {provider.id === "google_flow" && (
        <>
          <TextField
            label="Fallback Flow project id"
            value={draft.flowProjectId ?? provider.flowProjectId ?? ""}
            helpText={FLOW_PROJECT_ID_HELP_TEXT}
            isDisabled={isSaving}
            onChange={(flowProjectId) => onDraftChange({ flowProjectId })}
          />
          <GoogleFlowActions
            isPaused={remainingPauseSeconds > 0}
            isExtensionConnected={provider.extensionConnected === true}
          />
        </>
      )}
      {provider.kind !== "cli" && (
        <ProviderPacingFields
          maxConcurrent={draft.maxConcurrent ?? String(provider.maxConcurrent)}
          minIntervalS={draft.minIntervalS ?? String(provider.minIntervalS)}
          maxConcurrentHelpText={buildProviderHelpText(MAX_CONCURRENT_HELP_TEXT, provider.name)}
          minIntervalHelpText={buildMinIntervalHelpText(provider)}
          isDisabled={isSaving}
          onMaxConcurrentChange={(maxConcurrent) => onDraftChange({ maxConcurrent })}
          onMinIntervalChange={(minIntervalS) => onDraftChange({ minIntervalS })}
        />
      )}
      <ProviderModelsLine />
    </>
  );
}
