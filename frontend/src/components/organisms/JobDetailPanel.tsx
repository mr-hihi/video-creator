"use client";

import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { LinkButton } from "@/components/atoms/LinkButton";
import { Panel } from "@/components/atoms/Panel";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { JobStatusBadge } from "@/components/molecules/JobStatusBadge";
import { JobStepProgress } from "@/components/molecules/JobStepProgress";
import { JobSummary } from "@/components/molecules/JobSummary";
import { UNKNOWN_JOB_FAILURE_MESSAGE } from "@/features/jobs/constants";
import { useJobQuery } from "@/features/jobs/queries";
import type { JobDetail } from "@/features/jobs/types";
import { buildJobDownloadUrl } from "@/lib/api/client";
import { MarkdownPreview } from "./MarkdownPreview";

interface JobDetailPanelProps {
  jobId: string;
}

export function JobDetailPanel({ jobId }: JobDetailPanelProps) {
  const jobQuery = useJobQuery(jobId);

  if (jobQuery.isPending) return <PlaceholderMessage>Loading job…</PlaceholderMessage>;
  if (jobQuery.isError) return <ErrorAlert>{jobQuery.error.message}</ErrorAlert>;
  return <JobDetailContent job={jobQuery.data} />;
}

function JobDetailContent({ job }: { job: JobDetail }) {
  return (
    <div className="flex flex-col gap-6">
      <Panel title={job.sourceFilename} headerAction={<JobStatusBadge status={job.status} />}>
        <div className="flex flex-col gap-6">
          <JobSummary job={job} />
          <JobStepProgress job={job} />
          {job.status === "failed" && <ErrorAlert>{job.errorMessage ?? UNKNOWN_JOB_FAILURE_MESSAGE}</ErrorAlert>}
        </div>
      </Panel>
      {job.status === "done" && job.markdown !== null && (
        <Panel
          title="Result"
          headerAction={
            <LinkButton href={buildJobDownloadUrl(job.id)} download>
              Download .zip
            </LinkButton>
          }
        >
          <MarkdownPreview jobId={job.id} markdown={job.markdown} />
        </Panel>
      )}
    </div>
  );
}
