"use client";

import { useEffect, useState, type ReactNode } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { Panel } from "@/components/atoms/Panel";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { SuccessNotice } from "@/components/atoms/SuccessNotice";
import { SAVED_NOTICE } from "@/features/settings/constants";
import { useAppSettingsQuery, useUpdateAppSettingsMutation } from "@/features/settings/queries";
import type { AppSettings } from "@/features/settings/types";
import { buildSettingsUpdate, hasSettingsChanges } from "@/features/settings/utils";

const NO_DRAFT_SETTINGS: Partial<AppSettings> = {};

export interface AppSettingsFieldsProps {
  shownSettings: AppSettings;
  isDisabled: boolean;
  onChange: (changes: Partial<AppSettings>) => void;
}

interface AppSettingsFormProps {
  title: string;
  formKey: string;
  onUnsavedChangesChange: (formKey: string, hasUnsavedChanges: boolean) => void;
  renderFields: (fieldsProps: AppSettingsFieldsProps) => ReactNode;
}

interface AppSettingsDraftFieldsProps extends AppSettingsFormProps {
  settings: AppSettings;
}

export function AppSettingsForm(formProps: AppSettingsFormProps) {
  const { data: settings, error } = useAppSettingsQuery();

  if (!settings) {
    return error ? <ErrorAlert>{error.message}</ErrorAlert> : <PlaceholderMessage>Loading settings…</PlaceholderMessage>;
  }
  return (
    <Panel title={formProps.title}>
      <div className="flex flex-col gap-4">
        {error && <ErrorAlert>{error.message}</ErrorAlert>}
        <AppSettingsDraftFields settings={settings} {...formProps} />
      </div>
    </Panel>
  );
}

function AppSettingsDraftFields({ settings, formKey, onUnsavedChangesChange, renderFields }: AppSettingsDraftFieldsProps) {
  const [draftSettings, setDraftSettings] = useState(NO_DRAFT_SETTINGS);
  const [notice, setNotice] = useState<string>();
  const saveMutation = useUpdateAppSettingsMutation(() => {
    setDraftSettings(NO_DRAFT_SETTINGS);
    setNotice(SAVED_NOTICE);
  });
  const settingsUpdate = buildSettingsUpdate(settings, draftSettings);
  const hasUnsavedChanges = hasSettingsChanges(settingsUpdate);

  useEffect(() => {
    onUnsavedChangesChange(formKey, hasUnsavedChanges);
    return () => onUnsavedChangesChange(formKey, false);
  }, [formKey, hasUnsavedChanges, onUnsavedChangesChange]);

  function changeSettings(changes: Partial<AppSettings>) {
    setDraftSettings((currentDraft) => ({ ...currentDraft, ...changes }));
    setNotice(undefined);
  }

  return (
    <>
      {renderFields({
        shownSettings: { ...settings, ...draftSettings },
        isDisabled: saveMutation.isPending,
        onChange: changeSettings,
      })}
      <div className="flex flex-wrap items-center gap-2">
        <Button disabled={!hasUnsavedChanges || saveMutation.isPending} onClick={() => saveMutation.mutate(settingsUpdate)}>
          Save
        </Button>
      </div>
      {notice && <SuccessNotice>{notice}</SuccessNotice>}
      {saveMutation.error && <ErrorAlert>{saveMutation.error.message}</ErrorAlert>}
    </>
  );
}
