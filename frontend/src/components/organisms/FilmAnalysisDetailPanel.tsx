"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { Panel } from "@/components/atoms/Panel";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { JobStatusBadge } from "@/components/molecules/JobStatusBadge";
import { JobStepProgress } from "@/components/molecules/JobStepProgress";
import { JobSummary } from "@/components/molecules/JobSummary";
import { PromptsUsedList } from "@/components/molecules/PromptsUsedList";
import type { SummaryItem } from "@/components/molecules/SummaryList";
import { DELETE_ANALYSIS_CONFIRMATION, UNKNOWN_JOB_FAILURE_MESSAGE } from "@/features/jobs/constants";
import { useDeleteJobMutation, useJobQuery } from "@/features/jobs/queries";
import type { JobDetail } from "@/features/jobs/types";
import {
  canDeleteJob,
  canRerunJob,
  describeFrameCounts,
  hasAnyJobOutput,
  isFilmAnalysisJob,
} from "@/features/jobs/utils";
import { isNotFoundError } from "@/lib/api/client";
import { FilmRerunForm } from "./FilmRerunForm";
import { FilmResultTabs } from "./FilmResultTabs";
import { MakeFilmForm } from "./MakeFilmForm";
import { RerunSourceLink } from "./RerunSourceLink";

const FILM_ANALYSIS_PATH = "/film-analysis";

interface FilmAnalysisDetailPanelProps {
  jobId: string;
}

export function FilmAnalysisDetailPanel({ jobId }: FilmAnalysisDetailPanelProps) {
  const jobQuery = useJobQuery(jobId);

  if (jobQuery.isPending) return <PlaceholderMessage>Loading analysis…</PlaceholderMessage>;
  if (isNotFoundError(jobQuery.error)) return <AnalysisNotFound />;
  if (jobQuery.isError) return <ErrorAlert>{jobQuery.error.message}</ErrorAlert>;
  if (!isFilmAnalysisJob(jobQuery.data)) return <AnalysisNotFound />;
  return <FilmAnalysisDetailContent job={jobQuery.data} />;
}

function AnalysisNotFound() {
  return (
    <div className="flex flex-col items-center gap-2">
      <PlaceholderMessage>Analysis not found</PlaceholderMessage>
      <Link href={FILM_ANALYSIS_PATH} className="text-sm text-accent hover:underline">
        Back to Film Analysis
      </Link>
    </div>
  );
}

function FilmAnalysisDetailContent({ job }: { job: JobDetail }) {
  const router = useRouter();
  const deleteJobMutation = useDeleteJobMutation();

  function handleDelete() {
    if (!window.confirm(DELETE_ANALYSIS_CONFIRMATION)) return;
    deleteJobMutation.mutate(job.id, { onSuccess: () => router.push(FILM_ANALYSIS_PATH) });
  }

  return (
    <div className="flex flex-col gap-6">
      <Panel
        title={job.sourceFilename}
        headerAction={
          <div className="flex items-center gap-3">
            <JobStatusBadge status={job.status} />
            {canDeleteJob(job) && (
              <Button variant="secondary" disabled={deleteJobMutation.isPending} onClick={handleDelete}>
                Delete
              </Button>
            )}
          </div>
        }
      >
        <div className="flex flex-col gap-6">
          <JobSummary job={job} extraItems={buildFilmSummaryItems(job)} />
          <JobStepProgress job={job} />
          {job.status === "failed" && <ErrorAlert>{job.errorMessage ?? UNKNOWN_JOB_FAILURE_MESSAGE}</ErrorAlert>}
          {deleteJobMutation.isError && <ErrorAlert>{deleteJobMutation.error.message}</ErrorAlert>}
        </div>
      </Panel>
      {job.outputs !== null && hasAnyJobOutput(job.outputs) && (
        <Panel title="Result">
          <FilmResultTabs job={job} outputs={job.outputs} />
        </Panel>
      )}
      {job.options.prompts && (
        <details className="rounded-xl border border-border bg-surface p-4 shadow-sm sm:p-6">
          <summary className="cursor-pointer text-lg font-semibold">Prompts used</summary>
          <div className="mt-4">
            <PromptsUsedList prompts={job.options.prompts} />
          </div>
        </details>
      )}
      {canRerunJob(job) && (
        <Panel title="Rerun with another preset">
          <FilmRerunForm sourceJobId={job.id} />
        </Panel>
      )}
      {job.status === "done" && (
        <Panel title="Make a film">
          <MakeFilmForm job={job} />
        </Panel>
      )}
    </div>
  );
}

function buildFilmSummaryItems(job: JobDetail): SummaryItem[] {
  const frameItem = { term: "Frames", description: describeFrameCounts(job.options.frameCounts) };
  const rerunOfJobId = job.options.rerunOfJobId;
  if (!rerunOfJobId) return [frameItem];
  return [frameItem, { term: "Rerun of", description: <RerunSourceLink sourceJobId={rerunOfJobId} /> }];
}
