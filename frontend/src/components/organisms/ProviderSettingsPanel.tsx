"use client";

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { Panel } from "@/components/atoms/Panel";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { TabList } from "@/components/atoms/TabList";
import { UNSAVED_CHANGES_CONFIRMATION } from "@/features/promptPresets/constants";
import { PROVIDER_REFRESH_INTERVAL_MS, SECRET_KEY_MISSING_NOTICE } from "@/features/providers/constants";
import { useProviderSettingsQuery } from "@/features/providers/queries";
import type { ProviderId } from "@/features/providers/types";
import { resolveSelectedProvider } from "@/features/providers/utils";
import { buildProviderSettingsPath } from "@/features/settings/utils";
import { ProviderCard } from "./ProviderCard";

interface ProviderSettingsPanelProps {
  requestedProviderId: string | undefined;
  onUnsavedChangesChange: (formKey: string, hasUnsavedChanges: boolean) => void;
}

export function ProviderSettingsPanel({ requestedProviderId, onUnsavedChangesChange }: ProviderSettingsPanelProps) {
  const router = useRouter();
  const { data: providerSettings, error, dataUpdatedAt } = useProviderSettingsQuery(PROVIDER_REFRESH_INTERVAL_MS);
  const [hasUnsavedProviderChanges, setHasUnsavedProviderChanges] = useState(false);

  const reportProviderUnsavedChanges = useCallback(
    (formKey: string, hasFormUnsavedChanges: boolean) => {
      setHasUnsavedProviderChanges(hasFormUnsavedChanges);
      onUnsavedChangesChange(formKey, hasFormUnsavedChanges);
    },
    [onUnsavedChangesChange],
  );

  if (!providerSettings) {
    return error ? <ErrorAlert>{error.message}</ErrorAlert> : <PlaceholderMessage>Loading providers…</PlaceholderMessage>;
  }

  const selectedProvider = resolveSelectedProvider(providerSettings.providers, requestedProviderId);
  const providerTabs = providerSettings.providers.map((provider) => ({ value: provider.id, label: provider.name }));

  function selectProvider(providerId: ProviderId) {
    if (providerId === selectedProvider?.id) return;
    if (hasUnsavedProviderChanges && !window.confirm(UNSAVED_CHANGES_CONFIRMATION)) return;
    router.replace(buildProviderSettingsPath(providerId), { scroll: false });
  }

  return (
    <Panel title="Providers">
      <div className="flex flex-col gap-4">
        {error && <ErrorAlert>{error.message}</ErrorAlert>}
        {!providerSettings.secretKeySet && <ErrorAlert>{SECRET_KEY_MISSING_NOTICE}</ErrorAlert>}
        {selectedProvider && (
          <>
            <TabList label="Providers" value={selectedProvider.id} tabs={providerTabs} onChange={selectProvider} />
            <ProviderCard
              key={selectedProvider.id}
              provider={selectedProvider}
              isSecretKeySet={providerSettings.secretKeySet}
              referenceTimeMs={dataUpdatedAt}
              onUnsavedChangesChange={reportProviderUnsavedChanges}
            />
          </>
        )}
      </div>
    </Panel>
  );
}
