"use client";

import { useState } from "react";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import type { SelectOption } from "@/components/atoms/Select";
import {
  ALL_FILTER_LABEL,
  ALL_FILTER_VALUE,
  CAMERA_ANGLE_LABELS,
  SHOT_SIZE_LABELS,
} from "@/features/filmClones/constants";
import type {
  CameraAngle,
  CloneAsset,
  CloneImageOrientation,
  CloneShot,
  ShotSize,
} from "@/features/filmClones/types";
import { findAssetsByIds, labelsToSelectOptions } from "@/features/filmClones/utils";
import { CloneShotRow } from "./CloneShotRow";
import { SelectField } from "./SelectField";

type ShotSizeFilter = ShotSize | typeof ALL_FILTER_VALUE;
type CameraAngleFilter = CameraAngle | typeof ALL_FILTER_VALUE;

const ALL_FILTER_OPTION: SelectOption<typeof ALL_FILTER_VALUE> = { value: ALL_FILTER_VALUE, label: ALL_FILTER_LABEL };
const SHOT_SIZE_FILTER_OPTIONS = [ALL_FILTER_OPTION, ...labelsToSelectOptions(SHOT_SIZE_LABELS)];
const CAMERA_ANGLE_FILTER_OPTIONS = [ALL_FILTER_OPTION, ...labelsToSelectOptions(CAMERA_ANGLE_LABELS)];

interface CloneShotListProps {
  shots: readonly CloneShot[];
  assets: readonly CloneAsset[];
  jobId: string;
  frameOrientation: CloneImageOrientation;
  youtubeVideoId: string | undefined;
}

export function CloneShotList({ shots, assets, jobId, frameOrientation, youtubeVideoId }: CloneShotListProps) {
  const [shotSizeFilter, setShotSizeFilter] = useState<ShotSizeFilter>(ALL_FILTER_VALUE);
  const [cameraAngleFilter, setCameraAngleFilter] = useState<CameraAngleFilter>(ALL_FILTER_VALUE);

  const matchingShots = shots.filter(
    (shot) =>
      (shotSizeFilter === ALL_FILTER_VALUE || shot.shotSize === shotSizeFilter) &&
      (cameraAngleFilter === ALL_FILTER_VALUE || shot.cameraAngle === cameraAngleFilter),
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <SelectField<ShotSizeFilter>
          label="Shot size"
          value={shotSizeFilter}
          options={SHOT_SIZE_FILTER_OPTIONS}
          onChange={setShotSizeFilter}
        />
        <SelectField<CameraAngleFilter>
          label="Camera angle"
          value={cameraAngleFilter}
          options={CAMERA_ANGLE_FILTER_OPTIONS}
          onChange={setCameraAngleFilter}
        />
      </div>
      {matchingShots.length ? (
        <ul className="divide-y divide-border">
          {matchingShots.map((shot) => (
            <CloneShotRow
              key={shot.id}
              shot={shot}
              assets={findAssetsByIds(shot.assetIds, assets)}
              jobId={jobId}
              frameOrientation={frameOrientation}
              youtubeVideoId={youtubeVideoId}
            />
          ))}
        </ul>
      ) : (
        <PlaceholderMessage>No matching shots</PlaceholderMessage>
      )}
    </div>
  );
}
