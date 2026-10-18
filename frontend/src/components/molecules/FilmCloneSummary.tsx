import { EMPTY_VALUE_LABEL, TARGET_SETTING_LABEL } from "@/features/filmClones/constants";
import type { FilmCloneDetail } from "@/features/filmClones/types";
import {
  describeCloneAiUsed,
  describeScriptLanguage,
  describeTargetCountry,
} from "@/features/filmClones/utils";
import { describeCaptionKind, describeFrameCounts, describeLanguage } from "@/features/jobs/utils";
import { describePresetSnapshot } from "@/features/promptPresets/utils";
import { describeInputMode } from "@/features/settings/utils";
import { formatDateTime } from "@/lib/format";
import { SummaryList, type SummaryItem } from "./SummaryList";

interface FilmCloneSummaryProps {
  clone: FilmCloneDetail;
}

export function FilmCloneSummary({ clone }: FilmCloneSummaryProps) {
  return <SummaryList items={buildCloneSummaryItems(clone)} />;
}

function buildCloneSummaryItems(clone: FilmCloneDetail): SummaryItem[] {
  const jobOptions = clone.job?.options;
  const commonItems: SummaryItem[] = [
    { term: "Language", description: jobOptions ? describeLanguage(jobOptions.language) : EMPTY_VALUE_LABEL },
    { term: "Prompt preset", description: describePresetSnapshot(clone.preset) },
    { term: "AI", description: describeCloneAiUsed(clone) },
    { term: "Input", description: jobOptions ? describeInputMode(jobOptions.inputMode) : EMPTY_VALUE_LABEL },
    { term: "Frames", description: describeFrameCounts(jobOptions?.frameCounts) },
    { term: "Target country", description: describeTargetCountry(clone.targetCountry) },
    ...(clone.targetSetting ? [{ term: TARGET_SETTING_LABEL, description: clone.targetSetting }] : []),
    { term: "Script language", description: describeScriptLanguage(clone.scriptLanguage) },
    { term: "Created", description: formatDateTime(clone.createdAt) },
  ];
  const youtubeUrl = jobOptions?.url;
  if (!youtubeUrl) return commonItems;
  return [
    ...commonItems,
    {
      term: "Source",
      description: (
        <a href={youtubeUrl} target="_blank" rel="noreferrer" className="text-accent hover:underline">
          {youtubeUrl}
        </a>
      ),
    },
    { term: "Captions", description: describeCaptionKind(jobOptions.captionKind) },
  ];
}
