"use client";

import { useState } from "react";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { TabList } from "@/components/atoms/TabList";
import { CopyButton } from "@/components/molecules/CopyButton";
import { MISSING_OUTPUT_MESSAGE, WAITING_OUTPUT_MESSAGE, type FilmResultTab } from "@/features/jobs/constants";
import type { JobDetail, JobOutputs } from "@/features/jobs/types";
import { isJobInProgress, listFilmResultTabs } from "@/features/jobs/utils";
import { MarkdownPreview } from "./MarkdownPreview";

type OutputKey = keyof JobOutputs;

interface FilmResultTabsProps {
  job: JobDetail;
  outputs: JobOutputs;
}

export function FilmResultTabs({ job, outputs }: FilmResultTabsProps) {
  const resultTabs = listFilmResultTabs(job);
  const [selectedOutputKey, setSelectedOutputKey] = useState<OutputKey>(() =>
    findFirstFilledOutputKey(resultTabs, outputs),
  );
  const selectedOutput = outputs[selectedOutputKey];

  return (
    <div className="flex flex-col gap-4">
      <TabList<OutputKey>
        label="Result"
        value={selectedOutputKey}
        tabs={resultTabs.map(({ outputKey, label }) => ({ value: outputKey, label }))}
        onChange={setSelectedOutputKey}
      />
      {selectedOutput === null ? (
        <PlaceholderMessage>{isJobInProgress(job) ? WAITING_OUTPUT_MESSAGE : MISSING_OUTPUT_MESSAGE}</PlaceholderMessage>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="self-end">
            <CopyButton text={selectedOutput} />
          </div>
          <MarkdownPreview jobId={job.id} markdown={selectedOutput} />
        </div>
      )}
    </div>
  );
}

function findFirstFilledOutputKey(resultTabs: readonly FilmResultTab[], outputs: JobOutputs): OutputKey {
  const filledTab = resultTabs.find(({ outputKey }) => outputs[outputKey] !== null);
  return filledTab?.outputKey ?? resultTabs[0].outputKey;
}
