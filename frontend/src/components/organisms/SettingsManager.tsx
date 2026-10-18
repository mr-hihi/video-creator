"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TabList } from "@/components/atoms/TabList";
import { UNSAVED_CHANGES_CONFIRMATION } from "@/features/promptPresets/constants";
import {
  AI_MODELS_SETTINGS_TAB,
  FILM_CLONE_SETTINGS_TAB,
  FILM_STUDIO_SETTINGS_TAB,
  GENERAL_SETTINGS_TAB,
  PROMPT_OVERRIDE_SETTINGS_TAB,
  SETTINGS_TAB_OPTIONS,
  type SettingsTab,
} from "@/features/settings/constants";
import {
  buildSettingsPath,
  isInAppNavigationClick,
  resolveSettingsTab,
  updateUnsavedFormKeys,
} from "@/features/settings/utils";
import { AiModelsSettingsForm } from "./AiModelsSettingsForm";
import { FilmCloneSettingsForm } from "./FilmCloneSettingsForm";
import { FilmStudioSettingsForm } from "./FilmStudioSettingsForm";
import { GeneralSettingsForm } from "./GeneralSettingsForm";
import { PromptPresetManager } from "./PromptPresetManager";
import { ProviderSettingsPanel } from "./ProviderSettingsPanel";

const NO_UNSAVED_FORM_KEYS: ReadonlySet<string> = new Set();
const CAPTURE_PHASE_LISTENER_OPTIONS = { capture: true } as const;

interface SettingsManagerProps {
  requestedTab: string | undefined;
  requestedPresetId: string | undefined;
  requestedProviderId: string | undefined;
}

export function SettingsManager({ requestedTab, requestedPresetId, requestedProviderId }: SettingsManagerProps) {
  const router = useRouter();
  const selectedTab = resolveSettingsTab(requestedTab);
  const [unsavedFormKeys, setUnsavedFormKeys] = useState(NO_UNSAVED_FORM_KEYS);
  const hasUnsavedChanges = unsavedFormKeys.size > 0;

  useUnsavedChangesGuard(hasUnsavedChanges);

  const reportUnsavedChanges = useCallback((formKey: string, hasFormUnsavedChanges: boolean) => {
    setUnsavedFormKeys((currentFormKeys) => updateUnsavedFormKeys(currentFormKeys, formKey, hasFormUnsavedChanges));
  }, []);

  function selectTab(tab: SettingsTab) {
    if (tab === selectedTab) return;
    if (hasUnsavedChanges && !window.confirm(UNSAVED_CHANGES_CONFIRMATION)) return;
    router.replace(buildSettingsPath(tab), { scroll: false });
  }

  return (
    <div className="flex flex-col gap-6">
      <TabList label="Settings" value={selectedTab} tabs={SETTINGS_TAB_OPTIONS} onChange={selectTab} />
      {selectedTab === GENERAL_SETTINGS_TAB && (
        <>
          <GeneralSettingsForm onUnsavedChangesChange={reportUnsavedChanges} />
          <ProviderSettingsPanel
            requestedProviderId={requestedProviderId}
            onUnsavedChangesChange={reportUnsavedChanges}
          />
        </>
      )}
      {selectedTab === AI_MODELS_SETTINGS_TAB && <AiModelsSettingsForm onUnsavedChangesChange={reportUnsavedChanges} />}
      {selectedTab === PROMPT_OVERRIDE_SETTINGS_TAB && (
        <PromptPresetManager requestedPresetId={requestedPresetId} onUnsavedChangesChange={reportUnsavedChanges} />
      )}
      {selectedTab === FILM_CLONE_SETTINGS_TAB && <FilmCloneSettingsForm onUnsavedChangesChange={reportUnsavedChanges} />}
      {selectedTab === FILM_STUDIO_SETTINGS_TAB && <FilmStudioSettingsForm onUnsavedChangesChange={reportUnsavedChanges} />}
    </div>
  );
}

function useUnsavedChangesGuard(hasUnsavedChanges: boolean) {
  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const warnBeforeUnload = (event: BeforeUnloadEvent) => event.preventDefault();
    const confirmLeavingThroughLink = (event: MouseEvent) => {
      if (!isInAppNavigationClick(event) || window.confirm(UNSAVED_CHANGES_CONFIRMATION)) return;
      event.preventDefault();
    };
    window.addEventListener("beforeunload", warnBeforeUnload);
    window.addEventListener("click", confirmLeavingThroughLink, CAPTURE_PHASE_LISTENER_OPTIONS);
    return () => {
      window.removeEventListener("beforeunload", warnBeforeUnload);
      window.removeEventListener("click", confirmLeavingThroughLink, CAPTURE_PHASE_LISTENER_OPTIONS);
    };
  }, [hasUnsavedChanges]);
}
