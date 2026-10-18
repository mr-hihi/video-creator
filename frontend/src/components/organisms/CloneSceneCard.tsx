"use client";

import { useState } from "react";
import { AspectImage } from "@/components/atoms/AspectImage";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { CloneSceneHeading } from "@/components/molecules/CloneSceneHeading";
import { GeneratedImageView } from "@/components/molecules/GeneratedImageView";
import { TextAreaField } from "@/components/molecules/TextAreaField";
import {
  DESCRIPTION_MAX_LENGTH,
  DIALOGUE_MAX_LENGTH,
  EMPTY_VALUE_LABEL,
  IMAGE_PROMPT_MAX_LENGTH,
} from "@/features/filmClones/constants";
import { useGenerateSceneImageMutation, useUpdateCloneSceneMutation } from "@/features/filmClones/queries";
import type { CloneScene, CloneShot, FilmCloneDetail, SceneChanges } from "@/features/filmClones/types";
import {
  aspectToFrameOrientation,
  buildCloneFrameUrl,
  canEditCloneScenes,
  describeGenerateAction,
  describeSceneNumber,
  findAssetsByIds,
  haveSameFieldValues,
  isSceneGenerating,
  sceneToDraft,
} from "@/features/filmClones/utils";

interface CloneSceneCardProps {
  scene: CloneScene;
  shot: CloneShot | undefined;
  clone: FilmCloneDetail;
}

export function CloneSceneCard({ scene, shot, clone }: CloneSceneCardProps) {
  const updateSceneMutation = useUpdateCloneSceneMutation();
  const generateImageMutation = useGenerateSceneImageMutation();
  const [draft, setDraft] = useState<SceneChanges>(() => sceneToDraft(scene));

  const frameOrientation = aspectToFrameOrientation(clone.aspect);
  const sceneNumber = describeSceneNumber(scene);
  const isLocked =
    !canEditCloneScenes(clone) ||
    isSceneGenerating(scene, clone.generationRequests) ||
    updateSceneMutation.isPending ||
    generateImageMutation.isPending;
  const hasChanges = !haveSameFieldValues(draft, sceneToDraft(scene));
  const mutationError = updateSceneMutation.error ?? generateImageMutation.error;

  function updateDraft(field: keyof SceneChanges, value: string) {
    setDraft((currentDraft) => ({ ...currentDraft, [field]: value }));
  }

  function handleSave() {
    updateSceneMutation.mutate(
      { sceneId: scene.id, changes: draft },
      { onSuccess: (savedScene) => setDraft(sceneToDraft(savedScene)) },
    );
  }

  return (
    <article className="flex flex-col gap-4 rounded-lg border border-border p-4">
      <CloneSceneHeading scene={scene} shot={shot} assets={findAssetsByIds(scene.assetIds, clone.assets)} />
      <div className="grid gap-4 sm:grid-cols-2">
        <figure className="flex min-w-0 flex-col gap-2">
          <figcaption className="text-xs font-medium text-muted">Original</figcaption>
          <AspectImage
            src={shot ? buildCloneFrameUrl(clone.jobId, shot.frame) : undefined}
            alt={`${sceneNumber} original frame`}
            orientation={frameOrientation}
            fallbackText={EMPTY_VALUE_LABEL}
          />
        </figure>
        <figure className="flex min-w-0 flex-col gap-2">
          <figcaption className="text-xs font-medium text-muted">New</figcaption>
          <GeneratedImageView
            status={scene.imageStatus}
            path={scene.imagePath}
            error={scene.imageError}
            alt={`${sceneNumber} new image`}
            orientation={frameOrientation}
          />
          <div className="self-start">
            <Button variant="secondary" disabled={isLocked} onClick={() => generateImageMutation.mutate(scene.id)}>
              {describeGenerateAction(scene.imageStatus)}
            </Button>
          </div>
        </figure>
      </div>
      <TextAreaField
        label="Description"
        value={draft.description}
        maxLength={DESCRIPTION_MAX_LENGTH}
        isDisabled={isLocked}
        onChange={(description) => updateDraft("description", description)}
      />
      <TextAreaField
        label="Dialogue"
        value={draft.dialogue}
        maxLength={DIALOGUE_MAX_LENGTH}
        isDisabled={isLocked}
        onChange={(dialogue) => updateDraft("dialogue", dialogue)}
      />
      <TextAreaField
        label="Image prompt"
        value={draft.imagePrompt}
        maxLength={IMAGE_PROMPT_MAX_LENGTH}
        isDisabled={isLocked}
        onChange={(imagePrompt) => updateDraft("imagePrompt", imagePrompt)}
      />
      {mutationError && <ErrorAlert>{mutationError.message}</ErrorAlert>}
      <div className="self-start">
        <Button disabled={!hasChanges || isLocked} onClick={handleSave}>
          Save
        </Button>
      </div>
    </article>
  );
}
