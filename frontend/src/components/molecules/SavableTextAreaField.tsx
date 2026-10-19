"use client";

import { useState } from "react";
import { Button } from "@/components/atoms/Button";
import { useUnsavedChangesReport } from "@/lib/unsavedChanges";
import { TextAreaField } from "./TextAreaField";

interface SavableTextAreaFieldProps {
  label: string;
  savedValue: string;
  maxLength?: number;
  hint?: string;
  isDisabled: boolean;
  isSaving: boolean;
  onSave: (value: string) => void;
}

export function SavableTextAreaField({
  label,
  savedValue,
  maxLength,
  hint,
  isDisabled,
  isSaving,
  onSave,
}: SavableTextAreaFieldProps) {
  const [draftValue, setDraftValue] = useState<string>();
  const [trackedSavedValue, setTrackedSavedValue] = useState(savedValue);

  if (savedValue !== trackedSavedValue) {
    setTrackedSavedValue(savedValue);
    setDraftValue(undefined);
  }

  const shownValue = draftValue ?? savedValue;
  const hasUnsavedChanges = shownValue !== savedValue;
  const isLocked = isDisabled || isSaving;

  useUnsavedChangesReport(hasUnsavedChanges);

  return (
    <div className="flex flex-col gap-2">
      <TextAreaField
        label={label}
        value={shownValue}
        maxLength={maxLength}
        hint={hint}
        isDisabled={isLocked}
        onChange={setDraftValue}
      />
      <div className="self-start">
        <Button disabled={isLocked || !hasUnsavedChanges} onClick={() => onSave(shownValue)}>
          Save
        </Button>
      </div>
    </div>
  );
}
