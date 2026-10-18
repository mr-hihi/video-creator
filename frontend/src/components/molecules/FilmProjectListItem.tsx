import Link from "next/link";
import { Badge } from "@/components/atoms/Badge";
import { ORIENTATION_FRAME_LABELS } from "@/features/films/constants";
import type { FilmProject } from "@/features/films/types";
import { buildFilmProjectPath, describeCount } from "@/features/films/utils";
import { formatDateTime } from "@/lib/format";

interface FilmProjectListItemProps {
  project: FilmProject;
}

export function FilmProjectListItem({ project }: FilmProjectListItemProps) {
  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
      <div className="flex min-w-0 flex-1 basis-60 flex-col gap-1">
        <Link
          href={buildFilmProjectPath(project.id)}
          className="truncate text-sm font-medium hover:text-accent hover:underline"
        >
          {project.name}
        </Link>
        <span className="text-xs text-muted">
          {project.styleName} · {describeCount(project.episodeCount, "episodes")} ·{" "}
          <time dateTime={project.updatedAt}>{formatDateTime(project.updatedAt)}</time>
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Badge tone="neutral">{ORIENTATION_FRAME_LABELS[project.orientation]}</Badge>
      </div>
    </li>
  );
}
