"use client";

import Link from "next/link";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import {
  EMPTY_VALUE_LABEL,
  FOLLOW_TARGET_COUNTRY_SETTING,
  SCRIPT_LANGUAGE_FOLLOWS_COUNTRY_LABEL,
  SCRIPT_LANGUAGE_FROM_SETTINGS_LABEL,
} from "@/features/filmClones/constants";
import { SETTINGS_PATH } from "@/features/settings/constants";
import { useAppSettingsQuery } from "@/features/settings/queries";
import type { TargetCountryCode } from "@/features/filmClones/types";
import { describeScriptLanguage, findTranscriptLanguage, resolveScriptLanguage } from "@/features/filmClones/utils";

interface ScriptLanguagePreviewProps {
  targetCountry: TargetCountryCode | null;
  videoNotes: string | null;
}

export function ScriptLanguagePreview({ targetCountry, videoNotes }: ScriptLanguagePreviewProps) {
  const settingsQuery = useAppSettingsQuery();

  if (settingsQuery.isError) return <ErrorAlert>{settingsQuery.error.message}</ErrorAlert>;

  const setting = settingsQuery.data?.scriptLanguage;
  const languageName = setting
    ? describeScriptLanguage(resolveScriptLanguage(setting, targetCountry, findTranscriptLanguage(videoNotes)))
    : EMPTY_VALUE_LABEL;
  const settingOrigin =
    setting === FOLLOW_TARGET_COUNTRY_SETTING ? SCRIPT_LANGUAGE_FOLLOWS_COUNTRY_LABEL : SCRIPT_LANGUAGE_FROM_SETTINGS_LABEL;

  return (
    <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-sm">
      <span className="font-medium">Script language: {languageName}</span>
      {setting && <span className="text-muted">· {settingOrigin}</span>}
      <Link href={SETTINGS_PATH} className="text-xs text-accent hover:underline">
        Change in Settings
      </Link>
    </p>
  );
}
