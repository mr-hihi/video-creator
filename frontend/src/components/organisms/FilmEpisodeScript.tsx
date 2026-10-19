"use client";

import Link from "next/link";
import { AudioPlayer } from "@/components/atoms/AudioPlayer";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { Panel } from "@/components/atoms/Panel";
import { PromptsUsedList } from "@/components/molecules/PromptsUsedList";
import { SavableTextAreaField } from "@/components/molecules/SavableTextAreaField";
import { SummaryList, type SummaryItem } from "@/components/molecules/SummaryList";
import { EMPTY_VALUE_LABEL, EPISODE_SOURCE_LABELS, SUMMARY_HINT } from "@/features/films/constants";
import { useUpdateFilmEpisodeMutation } from "@/features/films/queries";
import type { EpisodeChanges, EpisodeDetail } from "@/features/films/types";
import {
  buildEpisodeSourcePath,
  buildFilmFileUrl,
  describeEpisodeAiUsed,
  describeMediaProgress,
  findQueuedRequest,
} from "@/features/films/utils";
import { DELETED_SOURCE_LABEL, MISSING_OUTPUT_MESSAGE } from "@/features/jobs/constants";
import { describePresetSnapshot } from "@/features/promptPresets/utils";
import { FilmCancelRequestButton } from "./FilmCancelRequestButton";

interface FilmEpisodeScriptProps {
  episode: EpisodeDetail;
  isLocked: boolean;
}

export function FilmEpisodeScript({ episode, isLocked }: FilmEpisodeScriptProps) {
  const updateEpisodeMutation = useUpdateFilmEpisodeMutation();
  const queuedMusicRequest = findQueuedRequest(episode.openRequests, (request) => request.kind === "music");

  function saveChanges(changes: EpisodeChanges) {
    updateEpisodeMutation.mutate({ episodeId: episode.id, changes });
  }

  return (
    <Panel title="Script">
      <div className="flex flex-col gap-5">
        <SummaryList items={buildScriptSummaryItems(episode)} />
        <SavableTextAreaField
          label="Summary"
          savedValue={episode.summary ?? ""}
          hint={SUMMARY_HINT}
          isDisabled={isLocked}
          isSaving={updateEpisodeMutation.isPending}
          onSave={(summary) => saveChanges({ summary })}
        />
        <div className="flex flex-col gap-2">
          <SavableTextAreaField
            label="Music prompt"
            savedValue={episode.musicPrompt ?? ""}
            isDisabled={isLocked}
            isSaving={updateEpisodeMutation.isPending}
            onSave={(musicPrompt) => saveChanges({ musicPrompt })}
          />
          {episode.musicPath ? (
            <AudioPlayer src={buildFilmFileUrl(episode.musicPath, episode.updatedAt)} label="Music" />
          ) : (
            <p className="text-xs text-muted">
              {describeMediaProgress(episode.musicStatus, episode.musicError) ?? MISSING_OUTPUT_MESSAGE}
            </p>
          )}
          {queuedMusicRequest && (
            <div className="flex flex-wrap gap-2">
              <FilmCancelRequestButton request={queuedMusicRequest} isDisabled={isLocked} />
            </div>
          )}
        </div>
        <SavableTextAreaField
          label="Thumbnail prompt"
          savedValue={episode.thumbnailPrompt ?? ""}
          isDisabled={isLocked}
          isSaving={updateEpisodeMutation.isPending}
          onSave={(thumbnailPrompt) => saveChanges({ thumbnailPrompt })}
        />
        {updateEpisodeMutation.isError && <ErrorAlert>{updateEpisodeMutation.error.message}</ErrorAlert>}
        <details className="rounded-lg border border-border bg-background px-3 py-2">
          <summary className="cursor-pointer text-sm font-medium">Prompts used</summary>
          <div className="mt-3">
            <PromptsUsedList
              prompts={{
                filmOutline: episode.filmOutlinePrompt,
                filmScript: episode.filmScriptPrompt,
                storyBible: episode.storyBiblePrompt,
              }}
            />
          </div>
        </details>
      </div>
    </Panel>
  );
}

function buildScriptSummaryItems(episode: EpisodeDetail): SummaryItem[] {
  return [
    { term: "Logline", description: episode.logline ?? EMPTY_VALUE_LABEL },
    { term: "Prompt preset", description: describePresetSnapshot(episode.preset) },
    { term: "AI", description: describeEpisodeAiUsed(episode) },
    { term: "Source", description: <EpisodeSourceDescription episode={episode} /> },
  ];
}

function EpisodeSourceDescription({ episode }: { episode: EpisodeDetail }) {
  if (episode.source === "idea") return EPISODE_SOURCE_LABELS.idea;
  const sourcePath = buildEpisodeSourcePath(episode);
  if (!sourcePath) return DELETED_SOURCE_LABEL;
  return (
    <Link href={sourcePath} className="text-accent hover:underline">
      {EPISODE_SOURCE_LABELS[episode.source]}
    </Link>
  );
}
