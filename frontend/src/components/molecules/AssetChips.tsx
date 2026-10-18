import { Badge } from "@/components/atoms/Badge";
import type { CloneAsset } from "@/features/filmClones/types";
import { describeAssetName } from "@/features/filmClones/utils";

interface AssetChipsProps {
  assets: readonly CloneAsset[];
}

export function AssetChips({ assets }: AssetChipsProps) {
  if (!assets.length) return null;
  return (
    <ul aria-label="Assets" className="flex flex-wrap gap-1.5">
      {assets.map((asset) => (
        <li key={asset.id}>
          <Badge tone="neutral">{describeAssetName(asset)}</Badge>
        </li>
      ))}
    </ul>
  );
}
