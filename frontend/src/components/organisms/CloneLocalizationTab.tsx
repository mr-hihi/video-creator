import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { LocalizationOverview } from "@/components/molecules/LocalizationOverview";
import type { FilmCloneDetail } from "@/features/filmClones/types";
import { describeMissingCloneContent, isCloneWaitingAt, isFilmCloneAnalyzing } from "@/features/filmClones/utils";
import { LocalizationChoicesForm } from "./LocalizationChoicesForm";
import { LocalizationReview } from "./LocalizationReview";

interface CloneLocalizationTabProps {
  clone: FilmCloneDetail;
}

export function CloneLocalizationTab({ clone }: CloneLocalizationTabProps) {
  if (isFilmCloneAnalyzing(clone)) return <PlaceholderMessage>{describeMissingCloneContent(clone)}</PlaceholderMessage>;
  if (isCloneWaitingAt(clone, "choosing_localization")) return <LocalizationChoicesForm clone={clone} />;
  if (isCloneWaitingAt(clone, "reviewing")) return <LocalizationReview clone={clone} />;
  return <LocalizationOverview clone={clone} />;
}
