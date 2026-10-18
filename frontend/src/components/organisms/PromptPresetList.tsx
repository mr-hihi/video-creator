"use client";

import { useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { Badge } from "@/components/atoms/Badge";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { TextField } from "@/components/molecules/TextField";
import {
  DEFAULT_PRESET_BADGE_LABEL,
  PRESET_EXPORT_ACCEPT,
  SYSTEM_PRESET_BADGE_LABEL,
} from "@/features/promptPresets/constants";
import { useCreatePromptPresetMutation, useImportPromptPresetMutation } from "@/features/promptPresets/queries";
import type { PromptPreset } from "@/features/promptPresets/types";
import { isValidPresetName } from "@/features/promptPresets/utils";
import { formatDateTime } from "@/lib/format";

const SELECTED_ROW_CLASS_NAME = "border-accent bg-accent/5";
const UNSELECTED_ROW_CLASS_NAME = "border-transparent hover:bg-foreground/5";

interface PromptPresetListProps {
  presets: readonly PromptPreset[];
  selectedPresetId: string | undefined;
  onSelect: (presetId: string) => void;
  onCreated: (presetId: string, notice?: string) => void;
}

export function PromptPresetList({ presets, selectedPresetId, onSelect, onCreated }: PromptPresetListProps) {
  const createMutation = useCreatePromptPresetMutation();
  const importMutation = useImportPromptPresetMutation();
  const importInputRef = useRef<HTMLInputElement>(null);
  const [isNaming, setIsNaming] = useState(false);
  const [newName, setNewName] = useState("");

  const failedMutation = [createMutation, importMutation].find((mutation) => mutation.isError);
  const isBusy = createMutation.isPending || importMutation.isPending;

  function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createMutation.mutate(newName, {
      onSuccess: (preset) => {
        setIsNaming(false);
        setNewName("");
        onCreated(preset.id);
      },
    });
  }

  function handleImportFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    importMutation.mutate(file, {
      onSuccess: (preset) => onCreated(preset.id, `Imported as '${preset.name}'`),
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <ul className="flex flex-col gap-1">
        {presets.map((preset) => (
          <li key={preset.id}>
            <button
              type="button"
              aria-current={preset.id === selectedPresetId ? "true" : undefined}
              onClick={() => onSelect(preset.id)}
              className={`flex w-full flex-col gap-1 rounded-lg border px-3 py-2 text-left transition-colors focus-visible:outline-2 focus-visible:outline-accent ${
                preset.id === selectedPresetId ? SELECTED_ROW_CLASS_NAME : UNSELECTED_ROW_CLASS_NAME
              }`}
            >
              <span className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium break-all">{preset.name}</span>
                {preset.isDefault && <Badge tone="info">{DEFAULT_PRESET_BADGE_LABEL}</Badge>}
                {preset.isSystem && <Badge tone="neutral">{SYSTEM_PRESET_BADGE_LABEL}</Badge>}
              </span>
              <span className="text-xs text-muted">
                v{preset.currentVersion} · <time dateTime={preset.updatedAt}>{formatDateTime(preset.updatedAt)}</time>
              </span>
            </button>
          </li>
        ))}
      </ul>
      {isNaming ? (
        <form onSubmit={handleCreate} className="flex flex-col gap-3">
          <TextField label="Name" value={newName} isDisabled={isBusy} onChange={setNewName} />
          <div className="flex gap-2">
            <Button type="submit" disabled={!isValidPresetName(newName) || isBusy}>
              Create
            </Button>
            <Button variant="secondary" disabled={isBusy} onClick={() => setIsNaming(false)}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" disabled={isBusy} onClick={() => setIsNaming(true)}>
            New preset
          </Button>
          <Button variant="secondary" disabled={isBusy} onClick={() => importInputRef.current?.click()}>
            Import
          </Button>
          <input
            ref={importInputRef}
            type="file"
            accept={PRESET_EXPORT_ACCEPT}
            hidden
            aria-label="Preset file"
            onChange={handleImportFile}
          />
        </div>
      )}
      {failedMutation?.error && <ErrorAlert>{failedMutation.error.message}</ErrorAlert>}
    </div>
  );
}
