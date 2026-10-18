import { CAMERA_ANGLE_LABELS, EMPTY_VALUE_LABEL, SHOT_SIZE_LABELS } from "@/features/filmClones/constants";
import type { CloneAsset, CloneScene, CloneShot } from "@/features/filmClones/types";
import { describeSceneNumber, describeShotTimestamp } from "@/features/filmClones/utils";
import { AssetChips } from "./AssetChips";

interface CloneSceneHeadingProps {
  scene: CloneScene;
  shot: CloneShot | undefined;
  assets: readonly CloneAsset[];
}

export function CloneSceneHeading({ scene, shot, assets }: CloneSceneHeadingProps) {
  const shotSize = shot?.shotSize ? SHOT_SIZE_LABELS[shot.shotSize] : EMPTY_VALUE_LABEL;
  const cameraAngle = shot?.cameraAngle ? CAMERA_ANGLE_LABELS[shot.cameraAngle] : EMPTY_VALUE_LABEL;

  return (
    <header className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
        <h4 className="text-base font-semibold">{describeSceneNumber(scene)}</h4>
        <span className="text-muted">·</span>
        <span className="tabular-nums">{describeShotTimestamp(shot)}</span>
        <span className="text-muted">·</span>
        <span>{shotSize}</span>
        <span className="text-muted">·</span>
        <span>{cameraAngle}</span>
      </div>
      <AssetChips assets={assets} />
    </header>
  );
}
