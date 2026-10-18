"use client";

import { useState } from "react";
import { AspectImage } from "@/components/atoms/AspectImage";
import { Badge } from "@/components/atoms/Badge";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { FileUploadButton } from "@/components/atoms/FileUploadButton";
import { EditPromptDialog } from "@/components/molecules/EditPromptDialog";
import {
  ACCEPTED_IMAGE_EXTENSIONS,
  DIFFERENT_STYLE_LABEL,
  EMPTY_VALUE_LABEL,
  ENTITY_TYPE_LABELS,
} from "@/features/films/constants";
import {
  useEditCharacterReferenceMutation,
  useGenerateCharacterReferenceMutation,
  useUnlinkProjectCharacterMutation,
  useUploadCharacterReferenceMutation,
} from "@/features/films/queries";
import type { FilmCharacter, FilmProjectDetail } from "@/features/films/types";
import {
  buildFilmFileUrl,
  describeGenerateLabel,
  describeMediaProgress,
  entityTypeToOrientation,
  findQueuedRequest,
  isMediaBusy,
} from "@/features/films/utils";
import { FilmCancelRequestButton } from "./FilmCancelRequestButton";

interface FilmCastCardProps {
  character: FilmCharacter;
  project: FilmProjectDetail;
  isReadOnly: boolean;
}

export function FilmCastCard({ character, project, isReadOnly }: FilmCastCardProps) {
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const generateMutation = useGenerateCharacterReferenceMutation();
  const editMutation = useEditCharacterReferenceMutation();
  const uploadMutation = useUploadCharacterReferenceMutation();
  const unlinkMutation = useUnlinkProjectCharacterMutation();

  const characterRequest = { projectId: project.id, characterId: character.id };
  const isPending =
    generateMutation.isPending || editMutation.isPending || uploadMutation.isPending || unlinkMutation.isPending;
  const isLocked = isReadOnly || isPending || isMediaBusy(character.referenceStatus);
  const referenceUrl = character.referencePath
    ? buildFilmFileUrl(character.referencePath, character.updatedAt)
    : undefined;
  const statusText = describeMediaProgress(character.referenceStatus, character.referenceError);
  const mutationError = generateMutation.error ?? uploadMutation.error ?? unlinkMutation.error;
  const queuedRequest = findQueuedRequest(project.openRequests, (request) => request.characterId === character.id);

  function applyEdit(prompt: string) {
    editMutation.mutate({ ...characterRequest, prompt }, { onSuccess: () => setIsEditDialogOpen(false) });
  }

  return (
    <li className="flex min-w-0 flex-col gap-3 rounded-lg border border-border p-4">
      <AspectImage
        src={referenceUrl}
        alt={`${character.name} reference`}
        orientation={entityTypeToOrientation(character.entityType)}
        fallbackText={EMPTY_VALUE_LABEL}
      />
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="min-w-0 text-sm font-semibold break-words">{character.name}</h3>
        <Badge tone="neutral">{ENTITY_TYPE_LABELS[character.entityType]}</Badge>
        {character.styleId !== project.styleId && <Badge tone="info">{DIFFERENT_STYLE_LABEL}</Badge>}
      </div>
      {statusText && <p className="text-xs break-words text-muted">{statusText}</p>}
      {mutationError && <ErrorAlert>{mutationError.message}</ErrorAlert>}
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" disabled={isLocked} onClick={() => generateMutation.mutate(characterRequest)}>
          {describeGenerateLabel(character.referenceStatus)}
        </Button>
        {character.referenceStatus === "done" && (
          <Button variant="secondary" disabled={isLocked} onClick={() => setIsEditDialogOpen(true)}>
            Edit image
          </Button>
        )}
        <FileUploadButton
          label="Upload"
          acceptedExtensions={ACCEPTED_IMAGE_EXTENSIONS}
          isDisabled={isLocked}
          onFileSelect={(file) => uploadMutation.mutate({ characterId: character.id, file })}
        />
        <FilmCancelRequestButton request={queuedRequest} isDisabled={isReadOnly} />
        <Button variant="secondary" disabled={isReadOnly || isPending} onClick={() => unlinkMutation.mutate(characterRequest)}>
          Remove from project
        </Button>
      </div>
      <EditPromptDialog
        title={`Edit ${character.name}`}
        isOpen={isEditDialogOpen}
        isSubmitting={editMutation.isPending}
        errorMessage={editMutation.error?.message}
        onApply={applyEdit}
        onClose={() => setIsEditDialogOpen(false)}
      />
    </li>
  );
}
