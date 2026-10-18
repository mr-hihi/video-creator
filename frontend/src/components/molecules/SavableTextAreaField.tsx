"use client";

import { useState } from "react";
import { Button } from "@/components/atoms/Button";
import { TextAreaField } from "./TextAreaField";

interface SavableTextAreaFieldProps {
  label: string;
  savedValue: string;
  isDisabled: boolean;
  isSaving: boolean;
  onSave: (value: string) => void;
}

export function SavableTextAreaField({ label, savedValue, isDisabled, isSaving, onSave }: SavableTextAreaFieldProps) {
  const [draftValue, setDraftValue] = useState<string>();
  const [trackedSavedValue, setTrackedSavedValue] = useState(savedValue);

  if (savedValue !== trackedSavedValue) {
    setTrackedSavedValue(savedValue);
    setDraftValue(undefined);
  }

  const shownValue = draftValue ?? savedValue;
  const isLocked = isDisabled || isSaving;

  return (
    <div className="flex flex-col gap-2">
      <TextAreaField label={label} value={shownValue} isDisabled={isLocked} onChange={setDraftValue} />
      <div className="self-start">
        <Button disabled={isLocked || shownValue === savedValue} onClick={() => onSave(shownValue)}>
          Save
        </Button>
      </div>
    </div>
  );
}
