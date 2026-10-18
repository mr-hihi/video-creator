import Link from "next/link";
import { AI_MODEL_LIST_SEPARATOR, AI_MODELS_SETTINGS_TAB, type SettingsTab } from "@/features/settings/constants";
import type { AiModelStatus, InputMode } from "@/features/settings/types";
import {
  buildMissingAiKeyHint,
  buildSettingsPath,
  describeAiModelLine,
  describeInputModeLine,
  listMissingAiProviderNames,
} from "@/features/settings/utils";

interface AiModelLineProps {
  status: AiModelStatus;
  inputMode?: InputMode;
  inputModeSettingsTab?: SettingsTab;
}

interface SettingsChangeLinkProps {
  settingsTab: SettingsTab;
}

export function AiModelLine({ status, inputMode, inputModeSettingsTab }: AiModelLineProps) {
  const aiModelPart = describeAiModelLine(status);
  const inputModePart = inputMode ? `${AI_MODEL_LIST_SEPARATOR}${describeInputModeLine(inputMode)}` : "";

  return (
    <div className="flex flex-col gap-1">
      <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-sm">
        <span className="font-medium">{inputModeSettingsTab ? aiModelPart : `${aiModelPart}${inputModePart}`}</span>
        <SettingsChangeLink settingsTab={AI_MODELS_SETTINGS_TAB} />
        {inputModeSettingsTab && (
          <>
            <span className="font-medium">{inputModePart}</span>
            <SettingsChangeLink settingsTab={inputModeSettingsTab} />
          </>
        )}
      </p>
      {listMissingAiProviderNames(status).map((providerName) => (
        <p key={providerName} className="text-xs text-muted">
          {buildMissingAiKeyHint(providerName)}
        </p>
      ))}
    </div>
  );
}

function SettingsChangeLink({ settingsTab }: SettingsChangeLinkProps) {
  return (
    <Link href={buildSettingsPath(settingsTab)} className="text-xs text-accent hover:underline">
      Change
    </Link>
  );
}
