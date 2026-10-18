"use client";

import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { FilmAnalysisListItem } from "@/components/molecules/FilmAnalysisListItem";
import { DELETE_ANALYSIS_CONFIRMATION, FILM_ANALYSIS_JOB_TYPES } from "@/features/jobs/constants";
import { useDeleteJobMutation, useJobsQuery } from "@/features/jobs/queries";

export function FilmAnalysisHistory() {
  const jobsQuery = useJobsQuery(FILM_ANALYSIS_JOB_TYPES);
  const deleteJobMutation = useDeleteJobMutation();

  function handleDelete(jobId: string) {
    if (!window.confirm(DELETE_ANALYSIS_CONFIRMATION)) return;
    deleteJobMutation.mutate(jobId);
  }

  if (jobsQuery.isPending) return <PlaceholderMessage>Loading analyses…</PlaceholderMessage>;
  if (jobsQuery.isError) return <ErrorAlert>{jobsQuery.error.message}</ErrorAlert>;
  if (jobsQuery.data.length === 0) return <PlaceholderMessage>No analyses yet</PlaceholderMessage>;

  return (
    <div className="flex flex-col gap-3">
      {deleteJobMutation.isError && <ErrorAlert>{deleteJobMutation.error.message}</ErrorAlert>}
      <ul className="divide-y divide-border">
        {jobsQuery.data.map((job) => (
          <FilmAnalysisListItem
            key={job.id}
            job={job}
            isDeleting={deleteJobMutation.isPending}
            onDelete={handleDelete}
          />
        ))}
      </ul>
    </div>
  );
}
