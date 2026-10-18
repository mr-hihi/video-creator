import Link from "next/link";
import { Badge } from "@/components/atoms/Badge";
import { Button } from "@/components/atoms/Button";
import { CLONE_SOURCE_LABELS } from "@/features/filmClones/constants";
import type { FilmClone } from "@/features/filmClones/types";
import {
  buildFilmCloneDetailPath,
  describeFilmCloneStep,
  describeTargetCountry,
  isFilmCloneBusy,
} from "@/features/filmClones/utils";
import { formatDateTime } from "@/lib/format";
import { CloneStatusBadge } from "./CloneStatusBadge";

interface FilmCloneListItemProps {
  clone: FilmClone;
  isDeleting: boolean;
  onDelete: (cloneId: string) => void;
}

export function FilmCloneListItem({ clone, isDeleting, onDelete }: FilmCloneListItemProps) {
  const detailPath = buildFilmCloneDetailPath(clone.id);

  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
      <div className="flex min-w-0 flex-1 basis-60 flex-col gap-1">
        <Link href={detailPath} className="truncate text-sm font-medium hover:text-accent hover:underline">
          {clone.sourceFilename}
        </Link>
        <span className="text-xs text-muted">
          {describeTargetCountry(clone.targetCountry)} · {describeFilmCloneStep(clone)} ·{" "}
          <time dateTime={clone.createdAt}>{formatDateTime(clone.createdAt)}</time>
        </span>
      </div>
      <Badge tone="neutral">{CLONE_SOURCE_LABELS[clone.sourceKind]}</Badge>
      <CloneStatusBadge status={clone.status} />
      <Link href={detailPath} className="text-sm text-accent hover:underline">
        View
      </Link>
      {!isFilmCloneBusy(clone) && (
        <Button variant="secondary" disabled={isDeleting} onClick={() => onDelete(clone.id)}>
          Delete
        </Button>
      )}
    </li>
  );
}
