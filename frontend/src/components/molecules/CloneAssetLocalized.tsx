import type { CloneAsset } from "@/features/filmClones/types";
import { describeAssetName, kindToReferenceOrientation } from "@/features/filmClones/utils";
import { GeneratedImageView } from "./GeneratedImageView";

interface CloneAssetLocalizedProps {
  asset: CloneAsset;
}

export function CloneAssetLocalized({ asset }: CloneAssetLocalizedProps) {
  const localizedName = describeAssetName(asset);

  return (
    <div className="flex min-w-0 flex-col gap-2">
      <GeneratedImageView
        status={asset.referenceStatus}
        path={asset.referencePath}
        error={asset.referenceError}
        alt={localizedName}
        orientation={kindToReferenceOrientation(asset.kind)}
      />
      <h4 className="text-sm font-semibold break-words">{localizedName}</h4>
      {asset.localizedDescription && (
        <p className="text-sm break-words whitespace-pre-wrap">{asset.localizedDescription}</p>
      )}
      {asset.localizationNote && <p className="text-xs break-words text-muted">{asset.localizationNote}</p>}
    </div>
  );
}
