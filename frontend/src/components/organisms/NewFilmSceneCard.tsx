"use client";

import type { SelectOption } from "@/components/atoms/Select";
import { FilmScenePromptsForm } from "@/components/molecules/FilmScenePromptsForm";
import { useCreateFilmSceneMutation } from "@/features/films/queries";
import type { ScenePromptsDraft } from "@/features/films/types";
import { createEmptyScenePromptsDraft, promptsDraftToFields } from "@/features/films/utils";

interface NewFilmSceneCardProps {
  episodeId: string;
  afterPosition: number | undefined;
  defaultClipDurationS: number;
  castOptions: readonly SelectOption<string>[];
  isLocked: boolean;
  onClose: () => void;
}

export function NewFilmSceneCard({
  episodeId,
  afterPosition,
  defaultClipDurationS,
  castOptions,
  isLocked,
  onClose,
}: NewFilmSceneCardProps) {
  const createSceneMutation = useCreateFilmSceneMutation();

  function createScene(draft: ScenePromptsDraft) {
    createSceneMutation.mutate(
      { episodeId, afterPosition, fields: promptsDraftToFields(draft) },
      { onSuccess: onClose },
    );
  }

  return (
    <article className="flex flex-col gap-4 rounded-lg border border-dashed border-accent/60 p-4">
      <h3 className="text-base font-semibold">New scene</h3>
      <FilmScenePromptsForm
        savedDraft={createEmptyScenePromptsDraft(defaultClipDurationS)}
        castOptions={castOptions}
        isDisabled={isLocked}
        isSaving={createSceneMutation.isPending}
        errorMessage={createSceneMutation.error?.message}
        onSave={createScene}
        onCancel={onClose}
      />
    </article>
  );
}
