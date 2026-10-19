"use client";

import { useState } from "react";
import { AspectImage } from "@/components/atoms/AspectImage";
import { Button } from "@/components/atoms/Button";
import { FileUploadButton } from "@/components/atoms/FileUploadButton";
import { EditPromptDialog } from "@/components/molecules/EditPromptDialog";
import { EnlargeableImage } from "@/components/molecules/EnlargeableImage";
import { FilmScenePart } from "@/components/molecules/FilmScenePart";
import type { GenerationKind, GenerationRequest } from "@/features/filmClones/types";
import { ACCEPTED_IMAGE_EXTENSIONS, MEDIA_STATUS_SEPARATOR } from "@/features/films/constants";
import { MISSING_OUTPUT_MESSAGE } from "@/features/jobs/constants";
import {
  useEditSceneImageMutation,
  useGenerateSceneMediaMutation,
  useUploadSceneImageMutation,
} from "@/features/films/queries";
import type { Orientation, Scene } from "@/features/films/types";
import {
  buildFilmFileUrl,
  describeBusyMedia,
  describeGenerateLabel,
  findQueuedRequest,
  findScenePassLabel,
  findSettledMediaError,
} from "@/features/films/utils";
import { FilmCancelRequestButton } from "./FilmCancelRequestButton";

const IMAGE_REQUEST_KINDS: readonly GenerationKind[] = ["scene_image", "edit_image"];

interface FilmSceneImagePartProps {
  scene: Scene;
  sceneNumber: number;
  openRequests: readonly GenerationRequest[];
  orientation: Orientation;
  isLocked: boolean;
  isSceneBusy: boolean;
}

export function FilmSceneImagePart({
  scene,
  sceneNumber,
  openRequests,
  orientation,
  isLocked,
  isSceneBusy,
}: FilmSceneImagePartProps) {
  const generateImageMutation = useGenerateSceneMediaMutation();
  const editImageMutation = useEditSceneImageMutation();
  const uploadImageMutation = useUploadSceneImageMutation();
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  const imageAlt = `Scene ${sceneNumber} image`;
  const busyLabel = describeBusyMedia(scene.imageStatus);
  const statusParts = [busyLabel, findScenePassLabel(scene.id, openRequests)].filter(Boolean);
  const isPending = generateImageMutation.isPending || editImageMutation.isPending || uploadImageMutation.isPending;
  const isActionLocked = isLocked || isSceneBusy || isPending;
  const actionError = generateImageMutation.error ?? uploadImageMutation.error;
  const queuedRequest = findQueuedRequest(
    openRequests,
    (request) => request.sceneId === scene.id && IMAGE_REQUEST_KINDS.includes(request.kind),
  );

  function applyEdit(prompt: string) {
    editImageMutation.mutate({ sceneId: scene.id, prompt }, { onSuccess: () => setIsEditDialogOpen(false) });
  }

  return (
    <FilmScenePart
      title="Image"
      media={
        scene.imagePath ? (
          <EnlargeableImage
            src={buildFilmFileUrl(scene.imagePath, scene.updatedAt)}
            alt={imageAlt}
            orientation={orientation}
          />
        ) : (
          <AspectImage src={undefined} alt={imageAlt} orientation={orientation} fallbackText={busyLabel ?? MISSING_OUTPUT_MESSAGE} />
        )
      }
      statusText={statusParts.length ? statusParts.join(MEDIA_STATUS_SEPARATOR) : undefined}
      errorMessage={findSettledMediaError(scene.imageStatus, scene.imageError)}
      actionErrorMessage={actionError?.message}
    >
      <Button
        variant="secondary"
        disabled={isActionLocked}
        onClick={() => generateImageMutation.mutate({ sceneId: scene.id, action: "generate-image" })}
      >
        {describeGenerateLabel(scene.imageStatus)}
      </Button>
      {scene.imageStatus === "done" && (
        <Button variant="secondary" disabled={isActionLocked} onClick={() => setIsEditDialogOpen(true)}>
          Edit
        </Button>
      )}
      <FileUploadButton
        label="Upload"
        acceptedExtensions={ACCEPTED_IMAGE_EXTENSIONS}
        isDisabled={isActionLocked}
        onFileSelect={(file) => uploadImageMutation.mutate({ sceneId: scene.id, file })}
      />
      <FilmCancelRequestButton request={queuedRequest} isDisabled={isLocked} />
      <EditPromptDialog
        title={`Edit scene ${sceneNumber} image`}
        isOpen={isEditDialogOpen}
        isSubmitting={editImageMutation.isPending}
        errorMessage={editImageMutation.error?.message}
        onApply={applyEdit}
        onClose={() => setIsEditDialogOpen(false)}
      />
    </FilmScenePart>
  );
}
