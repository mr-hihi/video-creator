"use client";

import { Badge } from "@/components/atoms/Badge";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import type { SelectOption } from "@/components/atoms/Select";
import { FilmScenePromptsForm } from "@/components/molecules/FilmScenePromptsForm";
import type { GenerationRequest } from "@/features/filmClones/types";
import { useDeleteFilmSceneMutation, useUpdateFilmSceneMutation } from "@/features/films/queries";
import type { FilmProjectDetail, Scene, ScenePromptsDraft } from "@/features/films/types";
import {
  buildDeleteSceneConfirmation,
  buildScenePromptChanges,
  isSceneBusy,
  sceneToPromptsDraft,
} from "@/features/films/utils";
import { FilmSceneClipPart } from "./FilmSceneClipPart";
import { FilmSceneImagePart } from "./FilmSceneImagePart";
import { FilmSceneNarrationPart } from "./FilmSceneNarrationPart";

interface FilmSceneCardProps {
  scene: Scene;
  sceneNumber: number;
  sceneCount: number;
  project: FilmProjectDetail;
  openRequests: readonly GenerationRequest[];
  castOptions: readonly SelectOption<string>[];
  isLocked: boolean;
  isInsertDisabled: boolean;
  onInsertAfter: () => void;
}

export function FilmSceneCard({
  scene,
  sceneNumber,
  sceneCount,
  project,
  openRequests,
  castOptions,
  isLocked,
  isInsertDisabled,
  onInsertAfter,
}: FilmSceneCardProps) {
  const moveSceneMutation = useUpdateFilmSceneMutation();
  const savePromptsMutation = useUpdateFilmSceneMutation();
  const deleteSceneMutation = useDeleteFilmSceneMutation();

  const isBusy = isSceneBusy(scene, openRequests);
  const isMenuLocked = isLocked || moveSceneMutation.isPending || deleteSceneMutation.isPending;
  const charactersById = new Map(project.characters.map((character) => [character.id, character]));
  const sceneCharacters = scene.characterIds.flatMap((characterId) => charactersById.get(characterId) ?? []);
  const menuError = moveSceneMutation.error ?? deleteSceneMutation.error;
  const partProps = {
    scene,
    sceneNumber,
    openRequests,
    orientation: project.orientation,
    isLocked,
    isSceneBusy: isBusy,
  };

  function moveTo(position: number) {
    moveSceneMutation.mutate({ sceneId: scene.id, changes: { position } });
  }

  function handleDelete() {
    if (!window.confirm(buildDeleteSceneConfirmation(sceneNumber))) return;
    deleteSceneMutation.mutate(scene.id);
  }

  function savePrompts(draft: ScenePromptsDraft) {
    savePromptsMutation.mutate({ sceneId: scene.id, changes: buildScenePromptChanges(draft, sceneToPromptsDraft(scene)) });
  }

  return (
    <article className="flex flex-col gap-4 rounded-lg border border-border p-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <h3 className="text-base font-semibold">Scene {sceneNumber}</h3>
          {sceneCharacters.map((character) => (
            <Badge key={character.id} tone="neutral">
              {character.name}
            </Badge>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" disabled={isMenuLocked || isInsertDisabled} onClick={onInsertAfter}>
            Insert scene after
          </Button>
          <Button variant="secondary" disabled={isMenuLocked || scene.position === 0} onClick={() => moveTo(scene.position - 1)}>
            Move up
          </Button>
          <Button
            variant="secondary"
            disabled={isMenuLocked || scene.position === sceneCount - 1}
            onClick={() => moveTo(scene.position + 1)}
          >
            Move down
          </Button>
          <Button variant="secondary" disabled={isMenuLocked || isBusy} onClick={handleDelete}>
            Delete
          </Button>
        </div>
      </header>
      {menuError && <ErrorAlert>{menuError.message}</ErrorAlert>}
      <div className={`grid gap-4 sm:grid-cols-2 ${project.allowNarration ? "lg:grid-cols-3" : ""}`}>
        <FilmSceneImagePart {...partProps} />
        <FilmSceneClipPart {...partProps} />
        {project.allowNarration && (
          <FilmSceneNarrationPart
            scene={scene}
            sceneNumber={sceneNumber}
            openRequests={openRequests}
            isLocked={isLocked}
            isSceneBusy={isBusy}
          />
        )}
      </div>
      <FilmScenePromptsForm
        savedDraft={sceneToPromptsDraft(scene)}
        castOptions={castOptions}
        isDisabled={isLocked}
        isSaving={savePromptsMutation.isPending}
        errorMessage={savePromptsMutation.error?.message}
        onSave={savePrompts}
      />
    </article>
  );
}
