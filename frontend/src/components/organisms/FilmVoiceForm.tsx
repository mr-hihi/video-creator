"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { FilePickerField } from "@/components/molecules/FilePickerField";
import { TextAreaField } from "@/components/molecules/TextAreaField";
import { TextField } from "@/components/molecules/TextField";
import {
  ACCEPTED_AUDIO_EXTENSIONS,
  CONSENT_CLIP_HINT,
  TRANSCRIBED_SAMPLE_TEXT_HINT,
} from "@/features/films/constants";
import {
  useCreateFilmVoiceMutation,
  useDeleteFilmVoiceMutation,
  useRemoveVoiceConsentMutation,
  useUpdateFilmVoiceMutation,
  useUploadVoiceConsentMutation,
} from "@/features/films/queries";
import type { VoiceDraft, VoiceTemplate } from "@/features/films/types";
import {
  buildDeleteVoiceConfirmation,
  createEmptyVoiceDraft,
  hasChangedFields,
  pickChangedFields,
  voiceToDraft,
} from "@/features/films/utils";

interface FilmVoiceFormProps {
  voice: VoiceTemplate | undefined;
  onClose: () => void;
}

export function FilmVoiceForm({ voice, onClose }: FilmVoiceFormProps) {
  const createMutation = useCreateFilmVoiceMutation();
  const updateMutation = useUpdateFilmVoiceMutation();
  const deleteMutation = useDeleteFilmVoiceMutation();
  const uploadConsentMutation = useUploadVoiceConsentMutation();
  const removeConsentMutation = useRemoveVoiceConsentMutation();
  const [draft, setDraft] = useState<VoiceDraft>(() => (voice ? voiceToDraft(voice) : createEmptyVoiceDraft()));
  const [sampleFile, setSampleFile] = useState<File>();
  const [consentFile, setConsentFile] = useState<File>();

  const changes = voice ? pickChangedFields(draft, voiceToDraft(voice)) : {};
  const isPending =
    createMutation.isPending ||
    updateMutation.isPending ||
    deleteMutation.isPending ||
    uploadConsentMutation.isPending ||
    removeConsentMutation.isPending;
  const hasInput = voice ? hasChangedFields(changes) || consentFile !== undefined : sampleFile !== undefined;
  const canSave = Boolean(draft.name.trim()) && hasInput && !isPending;
  const mutationError =
    createMutation.error ??
    updateMutation.error ??
    deleteMutation.error ??
    uploadConsentMutation.error ??
    removeConsentMutation.error;

  function updateDraft(draftChanges: Partial<VoiceDraft>) {
    setDraft((currentDraft) => ({ ...currentDraft, ...draftChanges }));
  }

  function uploadConsentThenClose(voiceId: string) {
    if (!consentFile) {
      onClose();
      return;
    }
    uploadConsentMutation.mutate({ voiceId, file: consentFile }, { onSuccess: onClose });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSave) return;
    if (!voice) {
      if (!sampleFile) return;
      createMutation.mutate(
        { file: sampleFile, ...draft, name: draft.name.trim() },
        { onSuccess: (createdVoice) => uploadConsentThenClose(createdVoice.id) },
      );
      return;
    }
    if (!hasChangedFields(changes)) {
      uploadConsentThenClose(voice.id);
      return;
    }
    updateMutation.mutate({ voiceId: voice.id, changes }, { onSuccess: () => uploadConsentThenClose(voice.id) });
  }

  function handleDelete(savedVoice: VoiceTemplate) {
    if (!window.confirm(buildDeleteVoiceConfirmation(savedVoice.name))) return;
    deleteMutation.mutate(savedVoice.id, { onSuccess: onClose });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <TextField label="Name" value={draft.name} isDisabled={isPending} onChange={(name) => updateDraft({ name })} />
      <TextField
        label="Description"
        value={draft.description}
        isDisabled={isPending}
        onChange={(description) => updateDraft({ description })}
      />
      {!voice && (
        <FilePickerField
          label="Sample"
          acceptedExtensions={ACCEPTED_AUDIO_EXTENSIONS}
          isDisabled={isPending}
          onFileSelect={setSampleFile}
        />
      )}
      <TextAreaField
        label="Sample text"
        value={draft.sampleText}
        hint={TRANSCRIBED_SAMPLE_TEXT_HINT}
        isDisabled={isPending}
        onChange={(sampleText) => updateDraft({ sampleText })}
      />
      <FilePickerField
        label="Consent clip"
        acceptedExtensions={ACCEPTED_AUDIO_EXTENSIONS}
        hint={CONSENT_CLIP_HINT}
        isDisabled={isPending}
        onFileSelect={setConsentFile}
      />
      {mutationError && <ErrorAlert>{mutationError.message}</ErrorAlert>}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={!canSave}>
          Save
        </Button>
        {voice?.consentPath && (
          <Button variant="secondary" disabled={isPending} onClick={() => removeConsentMutation.mutate(voice.id)}>
            Remove consent clip
          </Button>
        )}
        {voice && (
          <Button variant="secondary" disabled={isPending} onClick={() => handleDelete(voice)}>
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
