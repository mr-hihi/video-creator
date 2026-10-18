import Link from "next/link";
import { Badge } from "@/components/atoms/Badge";
import { JOB_SOURCE_LABELS } from "@/features/jobs/constants";
import type { Job } from "@/features/jobs/types";
import { buildJobDetailPath, describeCurrentJobStep } from "@/features/jobs/utils";
import { formatDateTime } from "@/lib/format";
import { JobStatusBadge } from "./JobStatusBadge";

interface JobListItemProps {
  job: Job;
}

export function JobListItem({ job }: JobListItemProps) {
  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
      <div className="flex min-w-0 flex-1 basis-60 flex-col gap-1">
        <Link href={buildJobDetailPath(job.id)} className="truncate text-sm font-medium hover:text-accent hover:underline">
          {job.sourceFilename}
        </Link>
        <span className="text-xs text-muted">
          {describeCurrentJobStep(job)} · <time dateTime={job.createdAt}>{formatDateTime(job.createdAt)}</time>
        </span>
      </div>
      <Badge tone="neutral">{JOB_SOURCE_LABELS[job.type]}</Badge>
      <JobStatusBadge status={job.status} />
      <Link href={buildJobDetailPath(job.id)} className="text-sm text-accent hover:underline">
        View
      </Link>
    </li>
  );
}
