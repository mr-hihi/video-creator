"use client";

import { useState } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import {
  PART_DURATION_LOWER_LIMIT_S,
  PART_DURATION_UPPER_LIMIT_S,
  PART_PLAN_MAX_LENGTH,
} from "@/features/films/constants";
import type { PartDraft } from "@/features/films/types";
import { hasChangedFields, partDraftToFields, pickChangedFields } from "@/features/films/utils";
import { useUnsavedChangesReport } from "@/lib/unsavedChanges";
import { NumberField } from "./NumberField";
import { TextAreaField } from "./TextAreaField";
import { TextField } from "./TextField";

interface FilmPartFormProps {
  savedDraft: PartDraft;
  isDisabled: boolean;
  isSaving: boolean;
  errorMessage: string | undefined;
  onSave: (draft: PartDraft) => void;
  onCancel: () => void;
}

export function FilmPartForm({ savedDraft, isDisabled, isSaving, errorMessage, onSave, onCancel }: FilmPartFormProps) {
  const [draft, setDraft] = useState(savedDraft);
  const isLocked = isDisabled || isSaving;
  const hasUnsavedChanges = hasChangedFields(pickChangedFields(draft, savedDraft));
  const canSave = hasUnsavedChanges && Number.isInteger(partDraftToFields(draft).targetDurationS);

  useUnsavedChangesReport(hasUnsavedChanges);

  function updateDraft(changes: Partial<PartDraft>) {
    setDraft((currentDraft) => ({ ...currentDraft, ...changes }));
  }

  return (
    <div className="flex flex-col gap-4">
      <TextField label="Title" value={draft.title} isDisabled={isLocked} onChange={(title) => updateDraft({ title })} />
      <TextAreaField
        label="Plan"
        value={draft.plan}
        maxLength={PART_PLAN_MAX_LENGTH}
        isDisabled={isLocked}
        onChange={(plan) => updateDraft({ plan })}
      />
      <NumberField
        label="Length (s)"
        value={draft.targetDurationText}
        min={PART_DURATION_LOWER_LIMIT_S}
        max={PART_DURATION_UPPER_LIMIT_S}
        isDisabled={isLocked}
        onChange={(targetDurationText) => updateDraft({ targetDurationText })}
      />
      {errorMessage && <ErrorAlert>{errorMessage}</ErrorAlert>}
      <div className="flex flex-wrap gap-2">
        <Button disabled={!canSave || isLocked} onClick={() => onSave(draft)}>
          Save
        </Button>
        <Button variant="secondary" disabled={isSaving} onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
