import type { CloneAsset, CloneImageOrientation } from "@/features/filmClones/types";
import { CloneAssetLocalized } from "./CloneAssetLocalized";
import { CloneAssetOriginal } from "./CloneAssetOriginal";

interface CloneAssetComparisonProps {
  asset: CloneAsset;
  jobId: string;
  frameOrientation: CloneImageOrientation;
}

export function CloneAssetComparison({ asset, jobId, frameOrientation }: CloneAssetComparisonProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <section className="flex min-w-0 flex-col gap-2">
        <h4 className="text-xs font-medium text-muted">Original</h4>
        <CloneAssetOriginal asset={asset} jobId={jobId} frameOrientation={frameOrientation} />
      </section>
      <section className="flex min-w-0 flex-col gap-2">
        <h4 className="text-xs font-medium text-muted">Localized</h4>
        <CloneAssetLocalized asset={asset} />
      </section>
    </div>
  );
}
