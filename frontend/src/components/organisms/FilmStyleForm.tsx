"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { TextAreaField } from "@/components/molecules/TextAreaField";
import { TextField } from "@/components/molecules/TextField";
import {
  NEGATIVE_PROMPT_MAX_LENGTH,
  SCENE_PREFIX_MAX_LENGTH,
  STYLE_INSTRUCTION_MAX_LENGTH,
} from "@/features/films/constants";
import {
  useCreateFilmStyleMutation,
  useDeleteFilmStyleMutation,
  useUpdateFilmStyleMutation,
} from "@/features/films/queries";
import type { FilmStyle, StyleDraft } from "@/features/films/types";
import {
  buildDeleteStyleConfirmation,
  createEmptyStyleDraft,
  hasChangedFields,
  pickChangedFields,
  styleDraftToFields,
  styleToDraft,
} from "@/features/films/utils";

interface FilmStyleFormProps {
  style: FilmStyle | undefined;
  onClose: () => void;
}

export function FilmStyleForm({ style, onClose }: FilmStyleFormProps) {
  const createMutation = useCreateFilmStyleMutation();
  const updateMutation = useUpdateFilmStyleMutation();
  const deleteMutation = useDeleteFilmStyleMutation();
  const [draft, setDraft] = useState<StyleDraft>(() => (style ? styleToDraft(style) : createEmptyStyleDraft()));

  const isBuiltin = style?.isBuiltin ?? false;
  const fields = styleDraftToFields(draft);
  const changes = style ? pickChangedFields(fields, styleDraftToFields(styleToDraft(style))) : fields;
  const isPending = createMutation.isPending || updateMutation.isPending || deleteMutation.isPending;
  const isLocked = isBuiltin || isPending;
  const hasRequiredFields = Boolean(draft.name.trim()) && Boolean(draft.styleInstruction.trim());
  const canSave = hasRequiredFields && hasChangedFields(changes) && !isLocked;
  const mutationError = createMutation.error ?? updateMutation.error ?? deleteMutation.error;

  function updateDraft(draftChanges: Partial<StyleDraft>) {
    setDraft((currentDraft) => ({ ...currentDraft, ...draftChanges }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSave) return;
    if (!style) {
      createMutation.mutate(fields, { onSuccess: onClose });
      return;
    }
    updateMutation.mutate({ styleId: style.id, changes }, { onSuccess: onClose });
  }

  function handleDelete(savedStyle: FilmStyle) {
    if (!window.confirm(buildDeleteStyleConfirmation(savedStyle.name))) return;
    deleteMutation.mutate(savedStyle.id, { onSuccess: onClose });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <TextField label="Name" value={draft.name} isDisabled={isLocked} onChange={(name) => updateDraft({ name })} />
      <TextAreaField
        label="Style instruction"
        value={draft.styleInstruction}
        maxLength={STYLE_INSTRUCTION_MAX_LENGTH}
        isDisabled={isLocked}
        onChange={(styleInstruction) => updateDraft({ styleInstruction })}
      />
      <TextAreaField
        label="Negative prompt"
        value={draft.negativePrompt}
        maxLength={NEGATIVE_PROMPT_MAX_LENGTH}
        isDisabled={isLocked}
        onChange={(negativePrompt) => updateDraft({ negativePrompt })}
      />
      <TextAreaField
        label="Scene prefix"
        value={draft.scenePrefix}
        maxLength={SCENE_PREFIX_MAX_LENGTH}
        isDisabled={isLocked}
        onChange={(scenePrefix) => updateDraft({ scenePrefix })}
      />
      <TextField
        label="Lighting"
        value={draft.lighting}
        isDisabled={isLocked}
        onChange={(lighting) => updateDraft({ lighting })}
      />
      {mutationError && <ErrorAlert>{mutationError.message}</ErrorAlert>}
      <div className="flex flex-wrap gap-2">
        {!isBuiltin && (
          <Button type="submit" disabled={!canSave}>
            Save
          </Button>
        )}
        {style && !isBuiltin && (
          <Button variant="secondary" disabled={isPending} onClick={() => handleDelete(style)}>
            Delete
          </Button>
        )}
        <Button variant="secondary" disabled={isPending} onClick={onClose}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
