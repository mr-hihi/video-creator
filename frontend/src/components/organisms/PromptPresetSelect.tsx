"use client";

import Link from "next/link";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { SelectField } from "@/components/molecules/SelectField";
import { usePromptPresetsQuery } from "@/features/promptPresets/queries";
import { buildPromptPresetsPath, describePresetOption, findDefaultPreset } from "@/features/promptPresets/utils";

const LOADING_OPTION = { value: "", label: "Loading presets…" };

interface PromptPresetSelectProps {
  selectedPresetId: string | undefined;
  isDisabled: boolean;
  onChange: (presetId: string) => void;
}

export function PromptPresetSelect({ selectedPresetId, isDisabled, onChange }: PromptPresetSelectProps) {
  const presetsQuery = usePromptPresetsQuery();

  if (presetsQuery.isError) return <ErrorAlert>{presetsQuery.error.message}</ErrorAlert>;

  const presets = presetsQuery.data ?? [];
  const shownPresetId = selectedPresetId ?? findDefaultPreset(presets)?.id ?? "";
  const options = presets.length
    ? presets.map((preset) => ({ value: preset.id, label: describePresetOption(preset) }))
    : [LOADING_OPTION];

  return (
    <div className="flex flex-col gap-1">
      <SelectField<string>
        label="Prompt preset"
        value={shownPresetId}
        options={options}
        isDisabled={isDisabled || presetsQuery.isPending}
        onChange={onChange}
      />
      {shownPresetId && (
        <Link href={buildPromptPresetsPath(shownPresetId)} className="self-start text-xs text-accent hover:underline">
          Edit presets
        </Link>
      )}
    </div>
  );
}
