"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { Panel } from "@/components/atoms/Panel";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { AiActivityLine } from "@/components/molecules/AiActivityLine";
import { CloneJobStepProgress } from "@/components/molecules/CloneJobStepProgress";
import { CloneStageBar } from "@/components/molecules/CloneStageBar";
import { CloneStatusBadge } from "@/components/molecules/CloneStatusBadge";
import { FilmCloneSummary } from "@/components/molecules/FilmCloneSummary";
import { PromptsUsedList } from "@/components/molecules/PromptsUsedList";
import {
  DELETE_CLONE_CONFIRMATION,
  FILM_CLONE_PATH,
  UNKNOWN_CLONE_FAILURE_MESSAGE,
} from "@/features/filmClones/constants";
import {
  useDeleteFilmCloneMutation,
  useFilmCloneQuery,
  useResumeFilmCloneMutation,
} from "@/features/filmClones/queries";
import type { FilmCloneDetail } from "@/features/filmClones/types";
import { canResumeFilmClone, isFilmCloneBusy } from "@/features/filmClones/utils";
import { SEND_TO_FILM_STUDIO_LABEL } from "@/features/films/constants";
import { isNotFoundError } from "@/lib/api/client";
import { FilmCloneTabs } from "./FilmCloneTabs";
import { SendCloneToFilmStudioForm } from "./SendCloneToFilmStudioForm";

interface FilmCloneDetailPanelProps {
  cloneId: string;
}

export function FilmCloneDetailPanel({ cloneId }: FilmCloneDetailPanelProps) {
  const cloneQuery = useFilmCloneQuery(cloneId);

  if (cloneQuery.isPending) return <PlaceholderMessage>Loading clone…</PlaceholderMessage>;
  if (isNotFoundError(cloneQuery.error)) return <CloneNotFound />;
  if (cloneQuery.isError) return <ErrorAlert>{cloneQuery.error.message}</ErrorAlert>;
  return <FilmCloneDetailContent clone={cloneQuery.data} fetchedAtMs={cloneQuery.dataUpdatedAt} />;
}

function CloneNotFound() {
  return (
    <div className="flex flex-col items-center gap-2">
      <PlaceholderMessage>Clone not found</PlaceholderMessage>
      <Link href={FILM_CLONE_PATH} className="text-sm text-accent hover:underline">
        Back to Film Clone
      </Link>
    </div>
  );
}

function FilmCloneDetailContent({ clone, fetchedAtMs }: { clone: FilmCloneDetail; fetchedAtMs: number }) {
  const router = useRouter();
  const deleteCloneMutation = useDeleteFilmCloneMutation();
  const [isSendDialogOpen, setIsSendDialogOpen] = useState(false);
  const usedPrompts = { ...clone.job?.options.prompts, ...clone.prompts };

  function handleDelete() {
    if (!window.confirm(DELETE_CLONE_CONFIRMATION)) return;
    deleteCloneMutation.mutate(clone.id, { onSuccess: () => router.push(FILM_CLONE_PATH) });
  }

  return (
    <div className="flex flex-col gap-6">
      <Panel
        title={clone.sourceFilename}
        headerAction={
          <div className="flex flex-wrap items-center gap-3">
            <CloneStatusBadge status={clone.status} />
            <Button disabled={clone.status !== "done"} onClick={() => setIsSendDialogOpen(true)}>
              {SEND_TO_FILM_STUDIO_LABEL}
            </Button>
            {!isFilmCloneBusy(clone) && (
              <Button variant="secondary" disabled={deleteCloneMutation.isPending} onClick={handleDelete}>
                Delete
              </Button>
            )}
          </div>
        }
      >
        <div className="flex flex-col gap-6">
          <CloneStageBar clone={clone} />
          {clone.status === "running" && clone.aiActivity && (
            <AiActivityLine activity={clone.aiActivity} nowMs={fetchedAtMs} />
          )}
          {clone.step === "analyzing" && clone.job && <CloneJobStepProgress job={clone.job} />}
          {clone.status === "failed" && <FilmCloneFailure clone={clone} />}
          {deleteCloneMutation.isError && <ErrorAlert>{deleteCloneMutation.error.message}</ErrorAlert>}
          <FilmCloneSummary clone={clone} />
          <FilmCloneTabs clone={clone} />
        </div>
      </Panel>
      {Object.keys(usedPrompts).length > 0 && (
        <details className="rounded-xl border border-border bg-surface p-4 shadow-sm sm:p-6">
          <summary className="cursor-pointer text-lg font-semibold">Prompts used</summary>
          <div className="mt-4">
            <PromptsUsedList prompts={usedPrompts} />
          </div>
        </details>
      )}
      {isSendDialogOpen && <SendCloneToFilmStudioForm clone={clone} onClose={() => setIsSendDialogOpen(false)} />}
    </div>
  );
}

function FilmCloneFailure({ clone }: { clone: FilmCloneDetail }) {
  const resumeCloneMutation = useResumeFilmCloneMutation();

  return (
    <div className="flex flex-col gap-3">
      <ErrorAlert>{clone.errorMessage ?? UNKNOWN_CLONE_FAILURE_MESSAGE}</ErrorAlert>
      {canResumeFilmClone(clone) && (
        <div className="self-start">
          <Button disabled={resumeCloneMutation.isPending} onClick={() => resumeCloneMutation.mutate(clone.id)}>
            Resume
          </Button>
        </div>
      )}
      {resumeCloneMutation.isError && <ErrorAlert>{resumeCloneMutation.error.message}</ErrorAlert>}
    </div>
  );
}
