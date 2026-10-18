"use client";

import { useState } from "react";
import { AspectImage, type ImageOrientation } from "@/components/atoms/AspectImage";
import type { CloneImageStatus } from "@/features/filmClones/types";
import { buildCloneFileUrl, describeImageProgress } from "@/features/filmClones/utils";
import { MISSING_OUTPUT_MESSAGE } from "@/features/jobs/constants";

interface GeneratedImageViewProps {
  status: CloneImageStatus;
  path: string | null;
  error: string | null;
  alt: string;
  orientation: ImageOrientation;
}

export function GeneratedImageView({ status, path, error, alt, orientation }: GeneratedImageViewProps) {
  const [trackedStatus, setTrackedStatus] = useState(status);
  const [imageVersion, setImageVersion] = useState(0);

  if (status !== trackedStatus) {
    setTrackedStatus(status);
    if (status === "done") setImageVersion(imageVersion + 1);
  }

  const imageUrl = status === "done" && path ? buildCloneFileUrl(path, imageVersion) : undefined;

  return (
    <AspectImage
      src={imageUrl}
      alt={alt}
      orientation={orientation}
      fallbackText={describeImageProgress(status, error) ?? MISSING_OUTPUT_MESSAGE}
    />
  );
}
