import { Badge, type BadgeTone } from "@/components/atoms/Badge";
import {
  CAMERA_ANGLE_LABELS,
  EMPTY_VALUE_LABEL,
  FRAME_KIND_LABELS,
  SHOT_SIZE_LABELS,
} from "@/features/filmClones/constants";
import type { CloneAsset, CloneImageOrientation, CloneShot, FrameKind } from "@/features/filmClones/types";
import { buildCloneFrameUrl, buildYoutubeTimestampUrl, formatTimestamp } from "@/features/filmClones/utils";
import { AssetChips } from "./AssetChips";
import { EnlargeableImage } from "./EnlargeableImage";

const FRAME_KIND_BADGE_TONES: Record<FrameKind, BadgeTone> = {
  dialogue: "info",
  scene: "neutral",
};

interface CloneShotRowProps {
  shot: CloneShot;
  assets: readonly CloneAsset[];
  jobId: string;
  frameOrientation: CloneImageOrientation;
  youtubeVideoId: string | undefined;
}

export function CloneShotRow({ shot, assets, jobId, frameOrientation, youtubeVideoId }: CloneShotRowProps) {
  const timestamp = formatTimestamp(shot.atMs);

  return (
    <li className="flex flex-col gap-3 py-4 sm:flex-row">
      <div className="w-full shrink-0 sm:w-48">
        <EnlargeableImage
          src={buildCloneFrameUrl(jobId, shot.frame)}
          alt={`Frame ${timestamp}`}
          orientation={frameOrientation}
        />
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {youtubeVideoId ? (
            <a
              href={buildYoutubeTimestampUrl(youtubeVideoId, shot.atMs)}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-accent tabular-nums hover:underline"
            >
              {timestamp}
            </a>
          ) : (
            <span className="font-medium tabular-nums">{timestamp}</span>
          )}
          <Badge tone={FRAME_KIND_BADGE_TONES[shot.frameKind]}>{FRAME_KIND_LABELS[shot.frameKind]}</Badge>
          <span>{shot.shotSize ? SHOT_SIZE_LABELS[shot.shotSize] : EMPTY_VALUE_LABEL}</span>
          <span className="text-muted">·</span>
          <span>{shot.cameraAngle ? CAMERA_ANGLE_LABELS[shot.cameraAngle] : EMPTY_VALUE_LABEL}</span>
        </div>
        <dl className="flex flex-col gap-1 text-sm">
          <div className="flex gap-2">
            <dt className="text-muted">Emotion</dt>
            <dd className="min-w-0 break-words">{shot.emotion ?? EMPTY_VALUE_LABEL}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="text-muted">Action</dt>
            <dd className="min-w-0 break-words">{shot.action ?? EMPTY_VALUE_LABEL}</dd>
          </div>
        </dl>
        <AssetChips assets={assets} />
      </div>
    </li>
  );
}
