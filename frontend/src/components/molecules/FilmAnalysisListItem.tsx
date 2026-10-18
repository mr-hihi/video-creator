import Link from "next/link";
import { Badge } from "@/components/atoms/Badge";
import { Button } from "@/components/atoms/Button";
import { JOB_SOURCE_LABELS } from "@/features/jobs/constants";
import type { Job } from "@/features/jobs/types";
import { buildFilmAnalysisDetailPath, canDeleteJob, describeCurrentJobStep } from "@/features/jobs/utils";
import { describePresetSnapshot } from "@/features/promptPresets/utils";
import { formatDateTime } from "@/lib/format";
import { JobStatusBadge } from "./JobStatusBadge";

interface FilmAnalysisListItemProps {
  job: Job;
  isDeleting: boolean;
  onDelete: (jobId: string) => void;
}

export function FilmAnalysisListItem({ job, isDeleting, onDelete }: FilmAnalysisListItemProps) {
  const detailPath = buildFilmAnalysisDetailPath(job.id);

  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
      <div className="flex min-w-0 flex-1 basis-60 flex-col gap-1">
        <Link href={detailPath} className="truncate text-sm font-medium hover:text-accent hover:underline">
          {job.sourceFilename}
        </Link>
        <span className="text-xs text-muted">
          {describePresetSnapshot(job.options.preset)} · {describeCurrentJobStep(job)} ·{" "}
          <time dateTime={job.createdAt}>{formatDateTime(job.createdAt)}</time>
        </span>
      </div>
      <Badge tone="neutral">{JOB_SOURCE_LABELS[job.type]}</Badge>
      <JobStatusBadge status={job.status} />
      <Link href={detailPath} className="text-sm text-accent hover:underline">
        View
      </Link>
      {canDeleteJob(job) && (
        <Button variant="secondary" disabled={isDeleting} onClick={() => onDelete(job.id)}>
          Delete
        </Button>
      )}
    </li>
  );
}
