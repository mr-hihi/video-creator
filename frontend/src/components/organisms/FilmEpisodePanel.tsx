"use client";

import Link from "next/link";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { FILMS_PATH } from "@/features/films/constants";
import { useFilmEpisodeQuery, useFilmProjectQuery } from "@/features/films/queries";
import type { FilmProjectDetail } from "@/features/films/types";
import { parseEpisodeNumber } from "@/features/films/utils";
import { isNotFoundError } from "@/lib/api/client";
import { FilmEpisodeHeader } from "./FilmEpisodeHeader";
import { FilmEpisodeOutline } from "./FilmEpisodeOutline";
import { FilmEpisodeResult } from "./FilmEpisodeResult";
import { FilmEpisodeScript } from "./FilmEpisodeScript";

interface FilmEpisodePanelProps {
  projectId: string;
  episodeNumberText: string;
  onClose?: () => void;
}

export function FilmEpisodePanel({ projectId, episodeNumberText, onClose }: FilmEpisodePanelProps) {
  const projectQuery = useFilmProjectQuery(projectId);
  const episodeNumber = parseEpisodeNumber(episodeNumberText);

  if (projectQuery.isPending) return <LoadingEpisode />;
  if (isNotFoundError(projectQuery.error)) return <EpisodeNotFound onClose={onClose} />;
  if (projectQuery.isError) return <ErrorAlert>{projectQuery.error.message}</ErrorAlert>;
  const episode = projectQuery.data.episodes.find((projectEpisode) => projectEpisode.number === episodeNumber);
  if (!episode) return projectQuery.isFetching ? <LoadingEpisode /> : <EpisodeNotFound onClose={onClose} />;
  return <FilmEpisodeWorkspace project={projectQuery.data} episodeId={episode.id} onClose={onClose} />;
}

function LoadingEpisode() {
  return <PlaceholderMessage>Loading episode…</PlaceholderMessage>;
}

interface EpisodeNotFoundProps {
  onClose: (() => void) | undefined;
}

function EpisodeNotFound({ onClose }: EpisodeNotFoundProps) {
  return (
    <div className="flex flex-col items-center gap-2">
      <PlaceholderMessage>Episode not found</PlaceholderMessage>
      {onClose ? (
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      ) : (
        <Link href={FILMS_PATH} className="text-sm text-accent hover:underline">
          Back to Film Studio
        </Link>
      )}
    </div>
  );
}

interface FilmEpisodeWorkspaceProps {
  project: FilmProjectDetail;
  episodeId: string;
  onClose: (() => void) | undefined;
}

function FilmEpisodeWorkspace({ project, episodeId, onClose }: FilmEpisodeWorkspaceProps) {
  const episodeQuery = useFilmEpisodeQuery(episodeId);

  if (episodeQuery.isPending) return <LoadingEpisode />;
  if (isNotFoundError(episodeQuery.error)) return <EpisodeNotFound onClose={onClose} />;
  if (episodeQuery.isError) return <ErrorAlert>{episodeQuery.error.message}</ErrorAlert>;

  const episode = episodeQuery.data;
  const isLocked = project.status === "archived" || episode.status === "running";

  return (
    <div className="flex flex-col gap-6">
      <FilmEpisodeHeader project={project} episode={episode} onClose={onClose} />
      <FilmEpisodeOutline project={project} episode={episode} />
      <FilmEpisodeScript episode={episode} isLocked={isLocked} />
      {episode.videoPath && <FilmEpisodeResult project={project} episode={episode} videoPath={episode.videoPath} />}
    </div>
  );
}
