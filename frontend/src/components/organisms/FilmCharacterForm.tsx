"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { FileUploadButton } from "@/components/atoms/FileUploadButton";
import { SelectField } from "@/components/molecules/SelectField";
import { TextAreaField } from "@/components/molecules/TextAreaField";
import { TextField } from "@/components/molecules/TextField";
import { labelsToSelectOptions } from "@/features/filmClones/utils";
import {
  ACCEPTED_IMAGE_EXTENSIONS,
  BUILT_IMAGE_PROMPT_HINT,
  CHARACTER_DESCRIPTION_MAX_LENGTH,
  ENTITY_TYPE_LABELS,
  IMAGE_PROMPT_MAX_LENGTH,
} from "@/features/films/constants";
import {
  useCreateFilmCharacterMutation,
  useDeleteFilmCharacterMutation,
  useFilmStylesQuery,
  useUpdateFilmCharacterMutation,
  useUploadCharacterReferenceMutation,
} from "@/features/films/queries";
import type { CharacterDraft, EntityType, FilmCharacter } from "@/features/films/types";
import {
  buildDeleteCharacterConfirmation,
  characterDraftToFields,
  characterToDraft,
  createEmptyCharacterDraft,
  hasChangedFields,
  isMediaBusy,
  pickChangedFields,
  stylesToOptions,
} from "@/features/films/utils";

const ENTITY_TYPE_OPTIONS = labelsToSelectOptions(ENTITY_TYPE_LABELS);

interface FilmCharacterFormProps {
  character: FilmCharacter | undefined;
  isReadOnly: boolean;
  onSaved: (character: FilmCharacter) => void;
  onClose: () => void;
}

export function FilmCharacterForm({ character, isReadOnly, onSaved, onClose }: FilmCharacterFormProps) {
  const stylesQuery = useFilmStylesQuery();
  const createMutation = useCreateFilmCharacterMutation();
  const updateMutation = useUpdateFilmCharacterMutation();
  const uploadMutation = useUploadCharacterReferenceMutation();
  const deleteMutation = useDeleteFilmCharacterMutation();
  const [draft, setDraft] = useState<CharacterDraft>(() =>
    character ? characterToDraft(character) : createEmptyCharacterDraft(),
  );

  const fields = characterDraftToFields(draft);
  const changes = character ? pickChangedFields(fields, characterDraftToFields(characterToDraft(character))) : fields;
  const isPending =
    createMutation.isPending || updateMutation.isPending || uploadMutation.isPending || deleteMutation.isPending;
  const isLocked = isReadOnly || isPending;
  const hasRequiredFields = Boolean(draft.name.trim()) && Boolean(draft.description.trim());
  const canSave = hasRequiredFields && hasChangedFields(changes) && !isLocked;
  const mutationError =
    createMutation.error ?? updateMutation.error ?? uploadMutation.error ?? deleteMutation.error ?? stylesQuery.error;

  function updateDraft(draftChanges: Partial<CharacterDraft>) {
    setDraft((currentDraft) => ({ ...currentDraft, ...draftChanges }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSave) return;
    if (!character) {
      createMutation.mutate(fields, { onSuccess: onSaved });
      return;
    }
    updateMutation.mutate({ characterId: character.id, changes }, { onSuccess: onSaved });
  }

  function handleDelete(savedCharacter: FilmCharacter) {
    if (!window.confirm(buildDeleteCharacterConfirmation(savedCharacter.name))) return;
    deleteMutation.mutate(savedCharacter.id, { onSuccess: onClose });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <TextField label="Name" value={draft.name} isDisabled={isLocked} onChange={(name) => updateDraft({ name })} />
      <SelectField<EntityType>
        label="Type"
        value={draft.entityType}
        options={ENTITY_TYPE_OPTIONS}
        isDisabled={isLocked}
        onChange={(entityType) => updateDraft({ entityType })}
      />
      <TextAreaField
        label="Description"
        value={draft.description}
        maxLength={CHARACTER_DESCRIPTION_MAX_LENGTH}
        isDisabled={isLocked}
        onChange={(description) => updateDraft({ description })}
      />
      <TextAreaField
        label="Image prompt"
        value={draft.imagePrompt}
        maxLength={IMAGE_PROMPT_MAX_LENGTH}
        hint={BUILT_IMAGE_PROMPT_HINT}
        isDisabled={isLocked}
        onChange={(imagePrompt) => updateDraft({ imagePrompt })}
      />
      <TextField
        label="Voice description"
        value={draft.voiceDescription}
        isDisabled={isLocked}
        onChange={(voiceDescription) => updateDraft({ voiceDescription })}
      />
      <SelectField<string>
        label="Style"
        value={draft.styleId}
        options={stylesToOptions(stylesQuery.data, draft.styleId)}
        isDisabled={isLocked}
        onChange={(styleId) => updateDraft({ styleId })}
      />
      {mutationError && <ErrorAlert>{mutationError.message}</ErrorAlert>}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={!canSave}>
          Save
        </Button>
        {character && (
          <>
            <FileUploadButton
              label="Upload reference"
              acceptedExtensions={ACCEPTED_IMAGE_EXTENSIONS}
              isDisabled={isLocked || isMediaBusy(character.referenceStatus)}
              onFileSelect={(file) => uploadMutation.mutate({ characterId: character.id, file })}
            />
            <Button variant="secondary" disabled={isLocked} onClick={() => handleDelete(character)}>
              Delete
            </Button>
          </>
        )}
        <Button variant="secondary" disabled={isPending} onClick={onClose}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
