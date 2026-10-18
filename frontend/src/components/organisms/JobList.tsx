"use client";

import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { JobListItem } from "@/components/molecules/JobListItem";
import { VIDEO_TO_MARKDOWN_JOB_TYPES } from "@/features/jobs/constants";
import { useJobsQuery } from "@/features/jobs/queries";

export function JobList() {
  const jobsQuery = useJobsQuery(VIDEO_TO_MARKDOWN_JOB_TYPES);

  if (jobsQuery.isPending) return <PlaceholderMessage>Loading jobs…</PlaceholderMessage>;
  if (jobsQuery.isError) return <ErrorAlert>{jobsQuery.error.message}</ErrorAlert>;
  if (jobsQuery.data.length === 0) {
    return <PlaceholderMessage>No jobs yet. Convert a video to create the first one.</PlaceholderMessage>;
  }

  return (
    <ul className="divide-y divide-border">
      {jobsQuery.data.map((job) => (
        <JobListItem key={job.id} job={job} />
      ))}
    </ul>
  );
}
