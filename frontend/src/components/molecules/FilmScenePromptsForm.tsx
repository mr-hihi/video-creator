"use client";

import { useState } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import type { SelectOption } from "@/components/atoms/Select";
import {
  EMPTY_VALUE_LABEL,
  IMAGE_PROMPT_MAX_LENGTH,
  NARRATION_MAX_LENGTH,
  SCENE_CLIP_DURATION_LOWER_LIMIT_S,
  SCENE_CLIP_DURATION_UPPER_LIMIT_S,
  VIDEO_PROMPT_MAX_LENGTH,
} from "@/features/films/constants";
import type { ScenePromptsDraft } from "@/features/films/types";
import { haveSameScenePrompts, isValidSceneClipDuration } from "@/features/films/utils";
import { CheckboxListField } from "./CheckboxListField";
import { NumberField } from "./NumberField";
import { TextAreaField } from "./TextAreaField";

interface FilmScenePromptsFormProps {
  savedDraft: ScenePromptsDraft;
  castOptions: readonly SelectOption<string>[];
  isDisabled: boolean;
  isSaving: boolean;
  errorMessage: string | undefined;
  onSave: (draft: ScenePromptsDraft) => void;
  onCancel?: () => void;
}

export function FilmScenePromptsForm({
  savedDraft,
  castOptions,
  isDisabled,
  isSaving,
  errorMessage,
  onSave,
  onCancel,
}: FilmScenePromptsFormProps) {
  const [draft, setDraft] = useState(savedDraft);
  const isLocked = isDisabled || isSaving;
  const hasUnsavedChanges = !haveSameScenePrompts(draft, savedDraft);
  const canSave = hasUnsavedChanges && isValidSceneClipDuration(draft.clipDurationS);

  function updateDraft(changes: Partial<ScenePromptsDraft>) {
    setDraft((currentDraft) => ({ ...currentDraft, ...changes }));
  }

  return (
    <div className="flex flex-col gap-4">
      <TextAreaField
        label="Image prompt"
        value={draft.imagePrompt}
        maxLength={IMAGE_PROMPT_MAX_LENGTH}
        isDisabled={isLocked}
        onChange={(imagePrompt) => updateDraft({ imagePrompt })}
      />
      <TextAreaField
        label="Video prompt"
        value={draft.videoPrompt}
        maxLength={VIDEO_PROMPT_MAX_LENGTH}
        isDisabled={isLocked}
        onChange={(videoPrompt) => updateDraft({ videoPrompt })}
      />
      <TextAreaField
        label="Narration"
        value={draft.narratorText}
        maxLength={NARRATION_MAX_LENGTH}
        isDisabled={isLocked}
        onChange={(narratorText) => updateDraft({ narratorText })}
      />
      <NumberField
        label="Clip length (s)"
        value={draft.clipDurationS}
        min={SCENE_CLIP_DURATION_LOWER_LIMIT_S}
        max={SCENE_CLIP_DURATION_UPPER_LIMIT_S}
        isDisabled={isLocked}
        onChange={(clipDurationS) => updateDraft({ clipDurationS })}
      />
      <CheckboxListField
        label="Characters"
        options={castOptions}
        selectedValues={draft.characterIds}
        emptyText={EMPTY_VALUE_LABEL}
        isDisabled={isLocked}
        onChange={(characterIds) => updateDraft({ characterIds })}
      />
      {errorMessage && <ErrorAlert>{errorMessage}</ErrorAlert>}
      <div className="flex flex-wrap gap-2">
        <Button disabled={!canSave || isLocked} onClick={() => onSave(draft)}>
          Save
        </Button>
        {onCancel && (
          <Button variant="secondary" disabled={isSaving} onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </div>
  );
}
