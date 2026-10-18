"use client";

import { useState, type ReactNode } from "react";
import { AspectImage } from "@/components/atoms/AspectImage";
import { Button } from "@/components/atoms/Button";
import { MEDIA_FAILED_LABEL_PREFIX, MEDIA_GENERATING_LABEL, MEDIA_QUEUED_LABEL, EMPTY_VALUE_LABEL } from "@/features/films/constants";
import type { ThumbnailCandidate } from "@/features/films/types";
import { buildFilmFileUrl, toFilmsRelativePath } from "@/features/films/utils";
import type { GenerationStatus } from "@/features/filmClones/types";

const CANDIDATE_STATUS_LABELS: Record<Exclude<GenerationStatus, "failed">, string> = {
  queued: MEDIA_QUEUED_LABEL,
  processing: MEDIA_GENERATING_LABEL,
  done: EMPTY_VALUE_LABEL,
  cancelled: EMPTY_VALUE_LABEL,
};

interface FilmThumbnailSlotProps {
  candidate: ThumbnailCandidate;
  isDisabled: boolean;
  cancelAction: ReactNode;
  onChoose: (candidateNumber: number) => void;
}

export function FilmThumbnailSlot({ candidate, isDisabled, cancelAction, onChoose }: FilmThumbnailSlotProps) {
  const [trackedStatus, setTrackedStatus] = useState(candidate.status);
  const [imageVersion, setImageVersion] = useState(0);

  if (candidate.status !== trackedStatus) {
    setTrackedStatus(candidate.status);
    if (candidate.status === "done") setImageVersion(imageVersion + 1);
  }

  const relativePath = candidate.path === null ? undefined : toFilmsRelativePath(candidate.path);
  const isReady = candidate.status === "done" && relativePath !== undefined;
  const imageUrl = isReady ? buildFilmFileUrl(relativePath, String(imageVersion)) : undefined;
  const alt = `Thumbnail candidate ${candidate.candidate}`;

  return (
    <figure className="flex min-w-0 flex-col gap-2">
      <AspectImage src={imageUrl} alt={alt} orientation="landscape" fallbackText={describeCandidateStatus(candidate)} />
      <figcaption className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        <span>{alt}</span>
        {cancelAction}
        {isReady && (
          <Button variant="secondary" disabled={isDisabled} onClick={() => onChoose(candidate.candidate)}>
            Use this
          </Button>
        )}
      </figcaption>
    </figure>
  );
}

function describeCandidateStatus(candidate: ThumbnailCandidate): string {
  if (candidate.status === "failed") return `${MEDIA_FAILED_LABEL_PREFIX}${candidate.errorMessage ?? EMPTY_VALUE_LABEL}`;
  return CANDIDATE_STATUS_LABELS[candidate.status];
}
