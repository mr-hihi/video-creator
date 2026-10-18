import type { Job } from "@/features/jobs/types";
import { describeCaptionKind, describeJobAiUsed, describeJobInputMode, describeLanguage } from "@/features/jobs/utils";
import { describePresetSnapshot } from "@/features/promptPresets/utils";
import { formatDateTime, formatOptionalDateTime } from "@/lib/format";
import { SummaryList, type SummaryItem } from "./SummaryList";

interface JobSummaryProps {
  job: Job;
  extraItems?: readonly SummaryItem[];
}

export function JobSummary({ job, extraItems = [] }: JobSummaryProps) {
  return <SummaryList items={[...buildSummaryItems(job), ...extraItems]} />;
}

function buildSummaryItems(job: Job): SummaryItem[] {
  const commonItems = [
    { term: "Language", description: describeLanguage(job.options.language) },
    { term: "Prompt preset", description: describePresetSnapshot(job.options.preset) },
    { term: "AI", description: describeJobAiUsed(job) },
    { term: "Input", description: describeJobInputMode(job) },
    { term: "Created", description: formatDateTime(job.createdAt) },
    { term: "Started", description: formatOptionalDateTime(job.startedAt) },
    { term: "Finished", description: formatOptionalDateTime(job.finishedAt) },
  ];
  const youtubeUrl = job.options.url;
  if (!youtubeUrl) return commonItems;
  return [
    ...commonItems,
    {
      term: "Source",
      description: (
        <a href={youtubeUrl} target="_blank" rel="noreferrer" className="text-accent hover:underline">
          {youtubeUrl}
        </a>
      ),
    },
    { term: "Captions", description: describeCaptionKind(job.options.captionKind) },
  ];
}
