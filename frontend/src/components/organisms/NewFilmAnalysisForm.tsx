"use client";

import { useState } from "react";
import { SegmentedControl } from "@/components/atoms/SegmentedControl";
import {
  CONVERSION_SOURCE_OPTIONS,
  DEFAULT_CONVERSION_SOURCE,
  type ConversionSource,
} from "@/features/jobs/constants";
import { useIsCreatingJob } from "@/features/jobs/queries";
import { FilmUploadForm } from "./FilmUploadForm";
import { FilmYoutubeForm } from "./FilmYoutubeForm";

export function NewFilmAnalysisForm() {
  const [source, setSource] = useState<ConversionSource>(DEFAULT_CONVERSION_SOURCE);
  const isCreatingJob = useIsCreatingJob();

  return (
    <div className="flex flex-col gap-5">
      <SegmentedControl<ConversionSource>
        label="Source"
        value={source}
        options={CONVERSION_SOURCE_OPTIONS}
        isDisabled={isCreatingJob}
        onChange={setSource}
      />
      {source === "upload" ? <FilmUploadForm /> : <FilmYoutubeForm />}
    </div>
  );
}
