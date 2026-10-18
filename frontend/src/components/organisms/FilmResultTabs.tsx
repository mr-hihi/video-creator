"use client";

import { useState } from "react";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { TabList } from "@/components/atoms/TabList";
import { CopyButton } from "@/components/molecules/CopyButton";
import { FILM_RESULT_TABS, MISSING_OUTPUT_MESSAGE, WAITING_OUTPUT_MESSAGE } from "@/features/jobs/constants";
import type { JobDetail, JobOutputs } from "@/features/jobs/types";
import { isJobInProgress } from "@/features/jobs/utils";
import { MarkdownPreview } from "./MarkdownPreview";

type OutputKey = keyof JobOutputs;

const RESULT_TAB_OPTIONS = FILM_RESULT_TABS.map(({ outputKey, label }) => ({ value: outputKey, label }));

interface FilmResultTabsProps {
  job: JobDetail;
  outputs: JobOutputs;
}

export function FilmResultTabs({ job, outputs }: FilmResultTabsProps) {
  const [selectedOutputKey, setSelectedOutputKey] = useState<OutputKey>(() => findFirstFilledOutputKey(outputs));
  const selectedOutput = outputs[selectedOutputKey];

  return (
    <div className="flex flex-col gap-4">
      <TabList<OutputKey>
        label="Result"
        value={selectedOutputKey}
        tabs={RESULT_TAB_OPTIONS}
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

function findFirstFilledOutputKey(outputs: JobOutputs): OutputKey {
  const filledTab = FILM_RESULT_TABS.find(({ outputKey }) => outputs[outputKey] !== null);
  return filledTab?.outputKey ?? FILM_RESULT_TABS[0].outputKey;
}
