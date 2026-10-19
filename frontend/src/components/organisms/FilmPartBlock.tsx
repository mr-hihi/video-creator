"use client";

import { useState } from "react";
import { Badge } from "@/components/atoms/Badge";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { FilmPartForm } from "@/components/molecules/FilmPartForm";
import {
  useDeleteFilmPartMutation,
  useRewriteFilmPartMutation,
  useUpdateFilmPartMutation,
} from "@/features/films/queries";
import type { EpisodeDetail, EpisodePartWithCounts, FilmProjectDetail, PartDraft } from "@/features/films/types";
import {
  buildDeletePartConfirmation,
  buildRewritePartConfirmation,
  describePartMediaProgress,
  describePartSceneCount,
  isPartRewriteShown,
  partDraftToFields,
  partToDraft,
  pickChangedFields,
  toPartNumber,
} from "@/features/films/utils";
import { FilmPartScenes } from "./FilmPartScenes";

const OPEN_PART_MARKER = "▾";
const CLOSED_PART_MARKER = "▸";

interface FilmPartBlockProps {
  project: FilmProjectDetail;
  episode: EpisodeDetail;
  part: EpisodePartWithCounts;
  isOpen: boolean;
  isLocked: boolean;
  isInsertDisabled: boolean;
  onToggle: () => void;
  onInsertAfter: () => void;
}

export function FilmPartBlock({
  project,
  episode,
  part,
  isOpen,
  isLocked,
  isInsertDisabled,
  onToggle,
  onInsertAfter,
}: FilmPartBlockProps) {
  const movePartMutation = useUpdateFilmPartMutation();
  const deletePartMutation = useDeleteFilmPartMutation();
  const rewritePartMutation = useRewriteFilmPartMutation();
  const [isEditing, setIsEditing] = useState(false);

  const partNumber = toPartNumber(part);
  const hasScenes = part.sceneCount > 0;
  const isMenuLocked =
    isLocked || movePartMutation.isPending || deletePartMutation.isPending || rewritePartMutation.isPending;
  const menuError = movePartMutation.error ?? deletePartMutation.error ?? rewritePartMutation.error;

  function moveTo(position: number) {
    movePartMutation.mutate({ partId: part.id, changes: { position } });
  }

  function handleDelete() {
    if (!window.confirm(buildDeletePartConfirmation(partNumber))) return;
    deletePartMutation.mutate(part.id);
  }

  function handleRewrite() {
    if (hasScenes && !window.confirm(buildRewritePartConfirmation(partNumber))) return;
    rewritePartMutation.mutate(part.id);
  }

  return (
    <article className="flex flex-col gap-4 rounded-lg border border-border p-4">
      <button
        type="button"
        aria-expanded={isOpen}
        onClick={onToggle}
        className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded text-left focus-visible:outline-2 focus-visible:outline-accent"
      >
        <span aria-hidden="true" className="text-muted">
          {isOpen ? OPEN_PART_MARKER : CLOSED_PART_MARKER}
        </span>
        <span className="min-w-0 text-base font-semibold break-words">{`Part ${partNumber} · ${part.title}`}</span>
        <span className="text-sm text-muted tabular-nums">{`${part.targetDurationS} s`}</span>
        <span className="text-sm text-muted">{describePartSceneCount(part)}</span>
        <span className="text-sm text-muted tabular-nums">{describePartMediaProgress(part)}</span>
        {part.failedCount > 0 && <Badge tone="danger">{`${part.failedCount} failed`}</Badge>}
      </button>
      {isEditing ? (
        <PartEditForm part={part} isLocked={isLocked} onClose={() => setIsEditing(false)} />
      ) : (
        <div className="flex flex-col gap-2">
          <p className="text-sm whitespace-pre-wrap break-words">{part.plan}</p>
          {part.recap && (
            <details className="rounded-lg border border-border bg-background px-3 py-2">
              <summary className="cursor-pointer text-sm font-medium">Recap</summary>
              <p className="mt-2 text-sm whitespace-pre-wrap break-words">{part.recap}</p>
            </details>
          )}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {!isEditing && (
          <Button variant="secondary" disabled={isMenuLocked} onClick={() => setIsEditing(true)}>
            Edit
          </Button>
        )}
        <Button variant="secondary" disabled={isMenuLocked || isInsertDisabled} onClick={onInsertAfter}>
          Insert part after
        </Button>
        <Button variant="secondary" disabled={isMenuLocked || part.position === 0} onClick={() => moveTo(part.position - 1)}>
          Move up
        </Button>
        <Button
          variant="secondary"
          disabled={isMenuLocked || part.position === episode.parts.length - 1}
          onClick={() => moveTo(part.position + 1)}
        >
          Move down
        </Button>
        {!hasScenes && (
          <Button variant="secondary" disabled={isMenuLocked} onClick={handleDelete}>
            Delete
          </Button>
        )}
        {isPartRewriteShown(episode, part) && (
          <Button variant="secondary" disabled={isMenuLocked} onClick={handleRewrite}>
            {hasScenes ? "Rewrite part" : "Write part"}
          </Button>
        )}
      </div>
      {menuError && <ErrorAlert>{menuError.message}</ErrorAlert>}
      {isOpen && <FilmPartScenes project={project} episode={episode} part={part} isLocked={isLocked} />}
    </article>
  );
}

interface PartEditFormProps {
  part: EpisodePartWithCounts;
  isLocked: boolean;
  onClose: () => void;
}

function PartEditForm({ part, isLocked, onClose }: PartEditFormProps) {
  const updatePartMutation = useUpdateFilmPartMutation();
  const savedDraft = partToDraft(part);

  function savePart(draft: PartDraft) {
    const changes = pickChangedFields(partDraftToFields(draft), partDraftToFields(savedDraft));
    updatePartMutation.mutate({ partId: part.id, changes }, { onSuccess: onClose });
  }

  return (
    <FilmPartForm
      savedDraft={savedDraft}
      isDisabled={isLocked}
      isSaving={updatePartMutation.isPending}
      errorMessage={updatePartMutation.error?.message}
      onSave={savePart}
      onCancel={onClose}
    />
  );
}
