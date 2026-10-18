"use client";

import { AspectImage } from "@/components/atoms/AspectImage";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { LinkButton } from "@/components/atoms/LinkButton";
import { Panel } from "@/components/atoms/Panel";
import { VideoPlayer } from "@/components/atoms/VideoPlayer";
import { FilmThumbnailSlot } from "@/components/molecules/FilmThumbnailSlot";
import { useChooseThumbnailMutation, useGenerateThumbnailsMutation } from "@/features/films/queries";
import type { EpisodeDetail, FilmProjectDetail } from "@/features/films/types";
import { buildEpisodeDownloadUrl, buildFilmFileUrl, describeDuration, findQueuedRequest } from "@/features/films/utils";
import { FilmCancelRequestButton } from "./FilmCancelRequestButton";

const CHOSEN_THUMBNAIL_LABEL = "Chosen thumbnail";

interface FilmEpisodeResultProps {
  project: FilmProjectDetail;
  episode: EpisodeDetail;
  videoPath: string;
}

export function FilmEpisodeResult({ project, episode, videoPath }: FilmEpisodeResultProps) {
  const generateThumbnailsMutation = useGenerateThumbnailsMutation();
  const chooseThumbnailMutation = useChooseThumbnailMutation();

  const isLocked = project.status === "archived" || episode.status === "running";
  const hasThumbnailsInProgress = episode.thumbnailCandidates.some(
    (candidate) => candidate.status === "queued" || candidate.status === "processing",
  );
  const isThumbnailBusy = generateThumbnailsMutation.isPending || chooseThumbnailMutation.isPending;
  const mutationError = generateThumbnailsMutation.error ?? chooseThumbnailMutation.error;
  const mediaVersion = episode.finishedAt ?? episode.updatedAt;

  return (
    <Panel title="Result">
      <div className="flex flex-col gap-5">
        <VideoPlayer
          src={buildFilmFileUrl(videoPath, mediaVersion)}
          label={`${episode.projectName} episode ${episode.number}`}
          orientation={project.orientation}
        />
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm tabular-nums">{describeDuration(episode.durationMs)}</span>
          <LinkButton href={buildEpisodeDownloadUrl(episode.id, "video")}>Download video</LinkButton>
          {episode.subtitlesPath && (
            <LinkButton variant="secondary" href={buildEpisodeDownloadUrl(episode.id, "subtitles")}>
              Download subtitles
            </LinkButton>
          )}
        </div>
        <div className="flex flex-col gap-3">
          <div className="self-start">
            <Button
              variant="secondary"
              disabled={isLocked || hasThumbnailsInProgress || isThumbnailBusy}
              onClick={() => generateThumbnailsMutation.mutate(episode.id)}
            >
              Generate thumbnails
            </Button>
          </div>
          {mutationError && <ErrorAlert>{mutationError.message}</ErrorAlert>}
          {episode.thumbnailCandidates.length > 0 && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {episode.thumbnailCandidates.map((candidate) => (
                <FilmThumbnailSlot
                  key={candidate.candidate}
                  candidate={candidate}
                  isDisabled={isLocked || isThumbnailBusy}
                  cancelAction={
                    <FilmCancelRequestButton
                      request={findQueuedRequest(
                        episode.openRequests,
                        (request) => request.kind === "thumbnail" && request.params.candidate === candidate.candidate,
                      )}
                      isDisabled={isLocked}
                    />
                  }
                  onChoose={(candidateNumber) =>
                    chooseThumbnailMutation.mutate({ episodeId: episode.id, candidate: candidateNumber })
                  }
                />
              ))}
            </div>
          )}
          {episode.thumbnailPath && (
            <div className="flex flex-col gap-2 sm:max-w-md">
              <AspectImage
                src={buildFilmFileUrl(episode.thumbnailPath, episode.updatedAt)}
                alt={CHOSEN_THUMBNAIL_LABEL}
                orientation="landscape"
                fallbackText={CHOSEN_THUMBNAIL_LABEL}
              />
              <div className="self-start">
                <LinkButton variant="secondary" href={buildEpisodeDownloadUrl(episode.id, "thumbnail")}>
                  Download thumbnail
                </LinkButton>
              </div>
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
}
