import { KEEP_ORIGINAL_LABEL, TARGET_SETTING_LABEL } from "@/features/filmClones/constants";
import type { FilmCloneDetail } from "@/features/filmClones/types";
import {
  aspectToFrameOrientation,
  describeScriptLanguage,
  describeTargetCountry,
} from "@/features/filmClones/utils";
import { CloneAssetComparison } from "./CloneAssetComparison";
import { LocalizationFlagFields } from "./LocalizationFlagFields";
import { SummaryList } from "./SummaryList";

interface LocalizationOverviewProps {
  clone: FilmCloneDetail;
}

export function LocalizationOverview({ clone }: LocalizationOverviewProps) {
  const changedAssets = clone.assets.filter((asset) => asset.changed);
  const frameOrientation = aspectToFrameOrientation(clone.aspect);
  const choiceItems = [
    {
      term: "Target country",
      description: clone.targetCountry ? describeTargetCountry(clone.targetCountry) : KEEP_ORIGINAL_LABEL,
    },
    ...(clone.targetSetting ? [{ term: TARGET_SETTING_LABEL, description: clone.targetSetting }] : []),
    { term: "Script language", description: describeScriptLanguage(clone.scriptLanguage) },
  ];

  return (
    <div className="flex flex-col gap-6">
      <SummaryList items={choiceItems} />
      <LocalizationFlagFields flags={clone} isCountryPicked isDisabled />
      {changedAssets.length > 0 && (
        <ul className="flex flex-col gap-4">
          {changedAssets.map((asset) => (
            <li key={asset.id} className="rounded-lg border border-border p-4">
              <CloneAssetComparison asset={asset} jobId={clone.jobId} frameOrientation={frameOrientation} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
