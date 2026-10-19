"use client";

import { FilmPartForm } from "@/components/molecules/FilmPartForm";
import { useCreateFilmPartMutation } from "@/features/films/queries";
import type { PartDraft } from "@/features/films/types";
import { createEmptyPartDraft, partDraftToFields } from "@/features/films/utils";

interface NewFilmPartFormProps {
  episodeId: string;
  afterPosition: number | undefined;
  isLocked: boolean;
  onClose: () => void;
}

export function NewFilmPartForm({ episodeId, afterPosition, isLocked, onClose }: NewFilmPartFormProps) {
  const createPartMutation = useCreateFilmPartMutation();

  function createPart(draft: PartDraft) {
    createPartMutation.mutate({ episodeId, afterPosition, fields: partDraftToFields(draft) }, { onSuccess: onClose });
  }

  return (
    <article className="flex flex-col gap-4 rounded-lg border border-dashed border-accent/60 p-4">
      <h3 className="text-base font-semibold">New part</h3>
      <FilmPartForm
        savedDraft={createEmptyPartDraft()}
        isDisabled={isLocked}
        isSaving={createPartMutation.isPending}
        errorMessage={createPartMutation.error?.message}
        onSave={createPart}
        onCancel={onClose}
      />
    </article>
  );
}
