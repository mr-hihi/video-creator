"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { LinkButton } from "@/components/atoms/LinkButton";
import { Panel } from "@/components/atoms/Panel";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { PromptSectionEditor } from "@/components/molecules/PromptSectionEditor";
import { TextField } from "@/components/molecules/TextField";
import { PROMPT_SECTIONS, SET_DEFAULT_FIRST_HINT } from "@/features/promptPresets/constants";
import {
  useDeletePromptPresetMutation,
  useDuplicatePromptPresetMutation,
  useMarkDefaultPromptPresetMutation,
  usePromptDefaultsQuery,
  usePromptPresetQuery,
  useSavePromptPresetMutation,
} from "@/features/promptPresets/queries";
import type { PresetPrompts, PromptDefaults, PromptKey, PromptPresetDetail } from "@/features/promptPresets/types";
import { areValidPrompts, haveSamePrompts, isValidPresetName } from "@/features/promptPresets/utils";
import { buildPromptPresetExportUrl } from "@/lib/api/client";
import { PromptPresetHistory } from "./PromptPresetHistory";

interface PromptPresetEditorProps {
  presetId: string;
  confirmDiscardingChanges: () => boolean;
  onNotice: (notice: string | undefined) => void;
  onOpenPreset: (presetId: string, notice?: string) => void;
  onDeleted: () => void;
  onUnsavedChangesChange: (hasUnsavedChanges: boolean) => void;
}

type PresetEditorFormProps = Omit<PromptPresetEditorProps, "presetId"> & {
  preset: PromptPresetDetail;
  defaults: PromptDefaults;
  isHistoryOpen: boolean;
  onHistoryOpenChange: (isHistoryOpen: boolean) => void;
};

export function PromptPresetEditor({ presetId, ...formProps }: PromptPresetEditorProps) {
  const presetQuery = usePromptPresetQuery(presetId);
  const defaultsQuery = usePromptDefaultsQuery();
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);

  if (presetQuery.isError) return <ErrorAlert>{presetQuery.error.message}</ErrorAlert>;
  if (defaultsQuery.isError) return <ErrorAlert>{defaultsQuery.error.message}</ErrorAlert>;
  if (presetQuery.isPending || defaultsQuery.isPending) return <PlaceholderMessage>Loading preset…</PlaceholderMessage>;

  const preset = presetQuery.data;
  return (
    <PresetEditorForm
      key={`${preset.currentVersion}:${preset.name}`}
      preset={preset}
      defaults={defaultsQuery.data}
      isHistoryOpen={isHistoryOpen}
      onHistoryOpenChange={setIsHistoryOpen}
      {...formProps}
    />
  );
}

function PresetEditorForm({
  preset,
  defaults,
  confirmDiscardingChanges,
  onNotice,
  onOpenPreset,
  onDeleted,
  onUnsavedChangesChange,
  isHistoryOpen,
  onHistoryOpenChange,
}: PresetEditorFormProps) {
  const saveMutation = useSavePromptPresetMutation((savedPreset) =>
    onNotice(
      savedPreset.currentVersion === preset.currentVersion
        ? `Renamed to '${savedPreset.name}'`
        : `Saved as v${savedPreset.currentVersion}`,
    ),
  );
  const markDefaultMutation = useMarkDefaultPromptPresetMutation();
  const duplicateMutation = useDuplicatePromptPresetMutation();
  const deleteMutation = useDeletePromptPresetMutation(onDeleted);
  const [draftName, setDraftName] = useState(preset.name);
  const [draftPrompts, setDraftPrompts] = useState<PresetPrompts>(preset.prompts);

  const hasUnsavedChanges = draftName !== preset.name || !haveSamePrompts(draftPrompts, preset.prompts);
  const isBusy = [saveMutation, markDefaultMutation, duplicateMutation, deleteMutation].some(
    (mutation) => mutation.isPending,
  );
  const failedMutation = [saveMutation, markDefaultMutation, duplicateMutation, deleteMutation].find(
    (mutation) => mutation.isError,
  );
  const canSave = hasUnsavedChanges && isValidPresetName(draftName) && areValidPrompts(draftPrompts) && !isBusy;

  useEffect(() => {
    onUnsavedChangesChange(hasUnsavedChanges);
  }, [hasUnsavedChanges, onUnsavedChangesChange]);

  function changePrompt(key: PromptKey, prompt: string) {
    setDraftPrompts((currentPrompts) => ({ ...currentPrompts, [key]: prompt }));
  }

  function discardChanges() {
    setDraftName(preset.name);
    setDraftPrompts(preset.prompts);
  }

  function save() {
    saveMutation.mutate({ presetId: preset.id, name: draftName, prompts: draftPrompts });
  }

  function markDefault() {
    markDefaultMutation.mutate(preset.id, {
      onSuccess: (markedPreset) => onNotice(`'${markedPreset.name}' is now the default`),
    });
  }

  function duplicate() {
    if (!confirmDiscardingChanges()) return;
    duplicateMutation.mutate(preset.id, { onSuccess: (copy) => onOpenPreset(copy.id) });
  }

  function remove() {
    if (!window.confirm(`Delete preset '${preset.name}'? Jobs that used it keep their prompts.`)) return;
    deleteMutation.mutate(preset.id);
  }

  function toggleHistory() {
    if (!isHistoryOpen && !confirmDiscardingChanges()) return;
    discardChanges();
    onHistoryOpenChange(!isHistoryOpen);
  }

  return (
    <Panel title="Editor">
      <div className="flex flex-col gap-6">
        <TextField label="Name" value={draftName} isDisabled={preset.isSystem || isBusy} onChange={setDraftName} />
        <div className="flex flex-wrap items-center gap-2">
          <Button disabled={!canSave} onClick={save}>
            Save
          </Button>
          <Button variant="secondary" disabled={!hasUnsavedChanges || isBusy} onClick={discardChanges}>
            Discard changes
          </Button>
          {!preset.isDefault && (
            <Button variant="secondary" disabled={isBusy} onClick={markDefault}>
              Set as default
            </Button>
          )}
          <Button variant="secondary" disabled={isBusy} onClick={duplicate}>
            Duplicate
          </Button>
          <LinkButton variant="secondary" href={buildPromptPresetExportUrl(preset.id)} download>
            Export
          </LinkButton>
          <Button variant="secondary" aria-expanded={isHistoryOpen} onClick={toggleHistory}>
            {isHistoryOpen ? "Close history" : "History"}
          </Button>
          {!preset.isSystem && (
            <Button
              variant="secondary"
              disabled={preset.isDefault || isBusy}
              title={preset.isDefault ? SET_DEFAULT_FIRST_HINT : undefined}
              onClick={remove}
            >
              Delete
            </Button>
          )}
        </div>
        {!preset.isSystem && preset.isDefault && <p className="text-xs text-muted">{SET_DEFAULT_FIRST_HINT}</p>}
        {failedMutation?.error && <ErrorAlert>{failedMutation.error.message}</ErrorAlert>}
        {isHistoryOpen && (
          <PromptPresetHistory presetId={preset.id} currentVersion={preset.currentVersion} onRestored={onNotice} />
        )}
        {PROMPT_SECTIONS.map((section) => (
          <PromptSectionEditor
            key={section.key}
            section={section}
            value={draftPrompts[section.key]}
            defaultValue={defaults.prompts[section.key]}
            appAddedPart={defaults.appAddedParts[section.key]}
            onChange={(prompt) => changePrompt(section.key, prompt)}
          />
        ))}
      </div>
    </Panel>
  );
}
