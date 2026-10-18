"use client";

import { useState } from "react";
import { SegmentedControl } from "@/components/atoms/SegmentedControl";
import { useIsCreatingFilmClone } from "@/features/filmClones/queries";
import {
  CONVERSION_SOURCE_OPTIONS,
  DEFAULT_CONVERSION_SOURCE,
  type ConversionSource,
} from "@/features/jobs/constants";
import { CloneUploadForm } from "./CloneUploadForm";
import { CloneYoutubeForm } from "./CloneYoutubeForm";

export function NewFilmCloneForm() {
  const [source, setSource] = useState<ConversionSource>(DEFAULT_CONVERSION_SOURCE);
  const isCreatingClone = useIsCreatingFilmClone();

  return (
    <div className="flex flex-col gap-5">
      <SegmentedControl<ConversionSource>
        label="Source"
        value={source}
        options={CONVERSION_SOURCE_OPTIONS}
        isDisabled={isCreatingClone}
        onChange={setSource}
      />
      {source === "upload" ? <CloneUploadForm /> : <CloneYoutubeForm />}
    </div>
  );
}
