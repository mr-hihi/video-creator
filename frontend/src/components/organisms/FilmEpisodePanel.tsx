"use client";

import Link from "next/link";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { FILMS_PATH } from "@/features/films/constants";
import { useFilmEpisodeQuery, useFilmProjectQuery } from "@/features/films/queries";
import type { FilmProjectDetail } from "@/features/films/types";
import { parseEpisodeNumber } from "@/features/films/utils";
import { isNotFoundError } from "@/lib/api/client";
import { FilmEpisodeHeader } from "./FilmEpisodeHeader";
import { FilmEpisodeResult } from "./FilmEpisodeResult";
import { FilmEpisodeScript } from "./FilmEpisodeScript";
import { FilmSceneList } from "./FilmSceneList";

interface FilmEpisodePanelProps {
  projectId: string;
  episodeNumberText: string;
}

export function FilmEpisodePanel({ projectId, episodeNumberText }: FilmEpisodePanelProps) {
  const projectQuery = useFilmProjectQuery(projectId);
  const episodeNumber = parseEpisodeNumber(episodeNumberText);

  if (projectQuery.isPending) return <LoadingEpisode />;
  if (isNotFoundError(projectQuery.error)) return <EpisodeNotFound />;
  if (projectQuery.isError) return <ErrorAlert>{projectQuery.error.message}</ErrorAlert>;
  const episode = projectQuery.data.episodes.find((projectEpisode) => projectEpisode.number === episodeNumber);
  if (!episode) return projectQuery.isFetching ? <LoadingEpisode /> : <EpisodeNotFound />;
  return <FilmEpisodeWorkspace project={projectQuery.data} episodeId={episode.id} />;
}

function LoadingEpisode() {
  return <PlaceholderMessage>Loading episode…</PlaceholderMessage>;
}

function EpisodeNotFound() {
  return (
    <div className="flex flex-col items-center gap-2">
      <PlaceholderMessage>Episode not found</PlaceholderMessage>
      <Link href={FILMS_PATH} className="text-sm text-accent hover:underline">
        Back to Film Studio
      </Link>
    </div>
  );
}

interface FilmEpisodeWorkspaceProps {
  project: FilmProjectDetail;
  episodeId: string;
}

function FilmEpisodeWorkspace({ project, episodeId }: FilmEpisodeWorkspaceProps) {
  const episodeQuery = useFilmEpisodeQuery(episodeId);

  if (episodeQuery.isPending) return <LoadingEpisode />;
  if (isNotFoundError(episodeQuery.error)) return <EpisodeNotFound />;
  if (episodeQuery.isError) return <ErrorAlert>{episodeQuery.error.message}</ErrorAlert>;

  const episode = episodeQuery.data;
  const isLocked = project.status === "archived" || episode.status === "running";

  return (
    <div className="flex flex-col gap-6">
      <FilmEpisodeHeader project={project} episode={episode} />
      <FilmSceneList project={project} episode={episode} />
      <FilmEpisodeScript episode={episode} isLocked={isLocked} />
      {episode.videoPath && <FilmEpisodeResult project={project} episode={episode} videoPath={episode.videoPath} />}
    </div>
  );
}
