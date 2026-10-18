import { AspectImage } from "@/components/atoms/AspectImage";
import { EMPTY_VALUE_LABEL } from "@/features/filmClones/constants";
import type { CloneAsset, CloneImageOrientation } from "@/features/filmClones/types";
import { buildCloneFrameUrl, describeFrameCount } from "@/features/filmClones/utils";

interface CloneAssetOriginalProps {
  asset: CloneAsset;
  jobId: string;
  frameOrientation: CloneImageOrientation;
}

export function CloneAssetOriginal({ asset, jobId, frameOrientation }: CloneAssetOriginalProps) {
  const frameUrl = asset.referenceFrame ? buildCloneFrameUrl(jobId, asset.referenceFrame) : undefined;

  return (
    <div className="flex min-w-0 flex-col gap-2">
      <AspectImage src={frameUrl} alt={asset.name} orientation={frameOrientation} fallbackText={EMPTY_VALUE_LABEL} />
      <div className="flex flex-col gap-0.5">
        <h4 className="text-sm font-semibold break-words">{asset.name}</h4>
        <p className="text-xs text-muted">
          {asset.culture} · {asset.period}
        </p>
      </div>
      <p className="text-sm break-words whitespace-pre-wrap">{asset.description}</p>
      <p className="text-xs text-muted">{describeFrameCount(asset.frames)}</p>
    </div>
  );
}
