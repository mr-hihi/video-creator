"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { Panel } from "@/components/atoms/Panel";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { SuccessNotice } from "@/components/atoms/SuccessNotice";
import { PROMPT_PRESETS_DESCRIPTION } from "@/features/promptPresets/constants";
import { usePromptPresetsQuery } from "@/features/promptPresets/queries";
import { buildPromptPresetsPath, findDefaultPreset } from "@/features/promptPresets/utils";
import { PROMPT_OVERRIDE_SETTINGS_TAB, PROMPT_PRESETS_FORM_KEY } from "@/features/settings/constants";
import { buildSettingsPath } from "@/features/settings/utils";
import { UNSAVED_CHANGES_CONFIRMATION } from "@/lib/unsavedChanges";
import { PromptPresetEditor } from "./PromptPresetEditor";
import { PromptPresetList } from "./PromptPresetList";

interface PromptPresetManagerProps {
  requestedPresetId: string | undefined;
  onUnsavedChangesChange: (formKey: string, hasUnsavedChanges: boolean) => void;
}

export function PromptPresetManager({ requestedPresetId, onUnsavedChangesChange }: PromptPresetManagerProps) {
  const router = useRouter();
  const presetsQuery = usePromptPresetsQuery();
  const [notice, setNotice] = useState<string>();
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  useEffect(() => {
    onUnsavedChangesChange(PROMPT_PRESETS_FORM_KEY, hasUnsavedChanges);
    return () => onUnsavedChangesChange(PROMPT_PRESETS_FORM_KEY, false);
  }, [hasUnsavedChanges, onUnsavedChangesChange]);

  const confirmDiscardingChanges = useCallback(
    () => !hasUnsavedChanges || window.confirm(UNSAVED_CHANGES_CONFIRMATION),
    [hasUnsavedChanges],
  );

  const openPreset = useCallback(
    (presetId: string, nextNotice?: string) => {
      setHasUnsavedChanges(false);
      setNotice(nextNotice);
      router.replace(buildPromptPresetsPath(presetId));
    },
    [router],
  );

  function selectPreset(presetId: string) {
    if (!confirmDiscardingChanges()) return;
    openPreset(presetId);
  }

  function handlePresetDeleted() {
    setHasUnsavedChanges(false);
    setNotice(undefined);
    router.replace(buildSettingsPath(PROMPT_OVERRIDE_SETTINGS_TAB));
  }

  if (presetsQuery.isPending) return <PlaceholderMessage>Loading presets…</PlaceholderMessage>;
  if (presetsQuery.isError) return <ErrorAlert>{presetsQuery.error.message}</ErrorAlert>;

  const presets = presetsQuery.data;
  const selectedPreset =
    presets.find((preset) => preset.id === requestedPresetId) ?? findDefaultPreset(presets) ?? presets[0];

  return (
    <div className="flex flex-col gap-6">
      <p className="max-w-prose text-sm text-muted">{PROMPT_PRESETS_DESCRIPTION}</p>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,3fr)]">
        <Panel title="Presets">
          <PromptPresetList
            presets={presets}
            selectedPresetId={selectedPreset?.id}
            onSelect={selectPreset}
            onCreated={openPreset}
          />
        </Panel>
        <div className="flex min-w-0 flex-col gap-4">
          {notice && <SuccessNotice>{notice}</SuccessNotice>}
          {selectedPreset && (
            <PromptPresetEditor
              key={selectedPreset.id}
              presetId={selectedPreset.id}
              confirmDiscardingChanges={confirmDiscardingChanges}
              onNotice={setNotice}
              onOpenPreset={openPreset}
              onDeleted={handlePresetDeleted}
              onUnsavedChangesChange={setHasUnsavedChanges}
            />
          )}
        </div>
      </div>
    </div>
  );
}
