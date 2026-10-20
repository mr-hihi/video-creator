import Link from "next/link";
import { AI_MODEL_LIST_SEPARATOR, AI_MODELS_SETTINGS_TAB, type SettingsTab } from "@/features/settings/constants";
import type { AiModelStatus } from "@/features/settings/types";
import {
  buildGoogleAiModelHint,
  buildMissingAiKeyHint,
  buildSettingsPath,
  describeAiModelLine,
  describeInputModeLine,
  listGroupsNeedingGoogleAi,
  listMissingAiProviderNames,
} from "@/features/settings/utils";

interface AiModelLineProps {
  status: AiModelStatus;
  inputModeSettingsTab?: SettingsTab;
}

interface SettingsChangeLinkProps {
  settingsTab: SettingsTab;
}

export function AiModelLine({ status, inputModeSettingsTab }: AiModelLineProps) {
  const aiModelPart = describeAiModelLine(status);
  const inputModePart = status.inputModeLabel
    ? `${AI_MODEL_LIST_SEPARATOR}${describeInputModeLine(status.inputModeLabel)}`
    : "";

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
      {listGroupsNeedingGoogleAi(status).map((group) => (
        <p key={group} className="text-xs text-muted">
          {buildGoogleAiModelHint(group)}
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
