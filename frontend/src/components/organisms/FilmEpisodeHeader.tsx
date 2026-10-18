"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { InfoNotice } from "@/components/atoms/InfoNotice";
import { Panel } from "@/components/atoms/Panel";
import { TextInput } from "@/components/atoms/TextInput";
import { FilmEpisodeStatusBadge } from "@/components/molecules/FilmEpisodeStatusBadge";
import { FilmStageList } from "@/components/molecules/FilmStageList";
import {
  EPISODE_ACTION_BY_STATUS,
  EPISODE_TITLE_MAX_LENGTH,
  NEEDS_ASSEMBLY_NOTICE,
  UNKNOWN_EPISODE_FAILURE_MESSAGE,
} from "@/features/films/constants";
import {
  useDeleteFilmEpisodeMutation,
  useEpisodeActionMutation,
  useLatestEpisodeActionError,
  useUpdateFilmEpisodeMutation,
} from "@/features/films/queries";
import type { EpisodeAction, EpisodeDetail, FilmProjectDetail } from "@/features/films/types";
import {
  buildDeleteEpisodeConfirmation,
  buildFilmProjectPath,
  canRewriteScript,
  countSceneProgress,
  describeEpisodeNumber,
  describePausedNotice,
  describeSceneProgress,
} from "@/features/films/utils";

interface FilmEpisodeHeaderProps {
  project: FilmProjectDetail;
  episode: EpisodeDetail;
}

export function FilmEpisodeHeader({ project, episode }: FilmEpisodeHeaderProps) {
  const router = useRouter();
  const projectPath = buildFilmProjectPath(project.id);
  const episodeActionMutation = useEpisodeActionMutation();
  const deleteEpisodeMutation = useDeleteFilmEpisodeMutation(() => router.push(projectPath));
  const latestActionError = useLatestEpisodeActionError(episode.id);
  const [isEditingTitle, setIsEditingTitle] = useState(false);

  const isReadOnly = project.status === "archived";
  const isRunning = episode.status === "running";
  const isBusy = episodeActionMutation.isPending || deleteEpisodeMutation.isPending;
  const isLocked = isReadOnly || isBusy;
  const statusAction = EPISODE_ACTION_BY_STATUS[episode.status];

  function runAction(action: EpisodeAction) {
    episodeActionMutation.mutate({ episodeId: episode.id, action });
  }

  function handleDelete() {
    if (!window.confirm(buildDeleteEpisodeConfirmation(episode.number))) return;
    deleteEpisodeMutation.mutate(episode.id);
  }

  return (
    <Panel
      title={`${describeEpisodeNumber(episode.number)} · ${episode.title}`}
      headerAction={
        <div className="flex flex-wrap items-center gap-3">
          <FilmEpisodeStatusBadge status={episode.status} />
          <Link href={projectPath} className="text-sm text-accent hover:underline">
            {project.name}
          </Link>
          {!isRunning && !isEditingTitle && (
            <Button variant="secondary" disabled={isReadOnly} onClick={() => setIsEditingTitle(true)}>
              Edit title
            </Button>
          )}
        </div>
      }
    >
      <div className="flex flex-col gap-5">
        {isEditingTitle && !isRunning && (
          <EpisodeTitleForm episode={episode} onClose={() => setIsEditingTitle(false)} />
        )}
        <div className="flex flex-wrap items-center gap-2">
          <Button disabled={isLocked} onClick={() => runAction(statusAction.action)}>
            {statusAction.label}
          </Button>
          {canRewriteScript(episode) && (
            <Button variant="secondary" disabled={isLocked} onClick={() => runAction("rewrite-script")}>
              Rewrite script
            </Button>
          )}
          {!isRunning && (
            <Button variant="secondary" disabled={isLocked} onClick={handleDelete}>
              Delete
            </Button>
          )}
        </div>
        {episode.status === "done" && episode.needsAssembly && <InfoNotice>{NEEDS_ASSEMBLY_NOTICE}</InfoNotice>}
        {latestActionError && <ErrorAlert>{latestActionError.message}</ErrorAlert>}
        {deleteEpisodeMutation.isError && <ErrorAlert>{deleteEpisodeMutation.error.message}</ErrorAlert>}
        <FilmStageList episode={episode} />
        {episode.status === "paused" && episode.step && episode.pausedStopPoint === episode.step && (
          <InfoNotice>{describePausedNotice(episode.step)}</InfoNotice>
        )}
        {episode.status === "failed" && <ErrorAlert>{episode.errorMessage ?? UNKNOWN_EPISODE_FAILURE_MESSAGE}</ErrorAlert>}
        <p className="text-sm tabular-nums">{describeSceneProgress(countSceneProgress(episode.scenes))}</p>
      </div>
    </Panel>
  );
}

interface EpisodeTitleFormProps {
  episode: EpisodeDetail;
  onClose: () => void;
}

function EpisodeTitleForm({ episode, onClose }: EpisodeTitleFormProps) {
  const updateEpisodeMutation = useUpdateFilmEpisodeMutation();
  const [title, setTitle] = useState(episode.title);
  const isSaving = updateEpisodeMutation.isPending;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim()) return;
    updateEpisodeMutation.mutate({ episodeId: episode.id, changes: { title } }, { onSuccess: onClose });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <TextInput
          type="text"
          value={title}
          maxLength={EPISODE_TITLE_MAX_LENGTH}
          aria-label="Title"
          autoComplete="off"
          disabled={isSaving}
          onChange={(event) => setTitle(event.target.value)}
        />
        <div className="flex gap-2">
          <Button type="submit" disabled={!title.trim() || title === episode.title || isSaving}>
            Save
          </Button>
          <Button variant="secondary" disabled={isSaving} onClick={onClose}>
            Cancel
          </Button>
        </div>
      </div>
      {updateEpisodeMutation.isError && <ErrorAlert>{updateEpisodeMutation.error.message}</ErrorAlert>}
    </form>
  );
}
