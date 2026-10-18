import Link from "next/link";
import type { Episode } from "@/features/films/types";
import {
  buildFilmEpisodePath,
  describeDuration,
  describeEpisodeNumber,
  describeEpisodeStep,
} from "@/features/films/utils";
import { formatDateTime } from "@/lib/format";
import { FilmEpisodeStatusBadge } from "./FilmEpisodeStatusBadge";

interface FilmEpisodeListItemProps {
  episode: Episode;
}

export function FilmEpisodeListItem({ episode }: FilmEpisodeListItemProps) {
  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
      <span className="text-sm font-semibold tabular-nums">{describeEpisodeNumber(episode.number)}</span>
      <div className="flex min-w-0 flex-1 basis-60 flex-col gap-1">
        <Link
          href={buildFilmEpisodePath(episode.projectId, episode.number)}
          className="truncate text-sm font-medium hover:text-accent hover:underline"
        >
          {episode.title}
        </Link>
        <span className="text-xs text-muted">
          {describeEpisodeStep(episode)} · <span className="tabular-nums">{describeDuration(episode.durationMs)}</span>{" "}
          · <time dateTime={episode.createdAt}>{formatDateTime(episode.createdAt)}</time>
        </span>
      </div>
      <FilmEpisodeStatusBadge status={episode.status} />
    </li>
  );
}
