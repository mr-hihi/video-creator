"use client";

import { useState } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { ASSET_KIND_LABELS } from "@/features/filmClones/constants";
import { useWriteCloneScriptMutation } from "@/features/filmClones/queries";
import type { CloneAsset, FilmCloneDetail } from "@/features/filmClones/types";
import { flagsToCandidateKinds } from "@/features/filmClones/utils";
import { LocalizedAssetCard } from "./LocalizedAssetCard";
import { RelocalizeButton } from "./RelocalizeButton";

interface LocalizationReviewProps {
  clone: FilmCloneDetail;
}

export function LocalizationReview({ clone }: LocalizationReviewProps) {
  const writeScriptMutation = useWriteCloneScriptMutation();
  const candidateKinds = flagsToCandidateKinds(clone);
  const changedAssets = clone.assets.filter((asset) => asset.changed);
  const unchangedCandidates = clone.assets.filter((asset) => !asset.changed && candidateKinds.has(asset.kind));
  const areReferencesReady = changedAssets.every((asset) => asset.referenceStatus === "done");

  return (
    <div className="flex flex-col gap-6">
      {changedAssets.length > 0 && (
        <ul className="flex flex-col gap-4">
          {changedAssets.map((asset) => (
            <li key={asset.id}>
              <LocalizedAssetCard asset={asset} clone={clone} />
            </li>
          ))}
        </ul>
      )}
      {unchangedCandidates.length > 0 && (
        <ul className="flex flex-col gap-2">
          {unchangedCandidates.map((asset) => (
            <UnchangedCandidate key={asset.id} asset={asset} clone={clone} />
          ))}
        </ul>
      )}
      {writeScriptMutation.isError && <ErrorAlert>{writeScriptMutation.error.message}</ErrorAlert>}
      <div className="flex flex-wrap items-start gap-3">
        <Button
          disabled={!areReferencesReady || writeScriptMutation.isPending}
          onClick={() => writeScriptMutation.mutate(clone.id)}
        >
          Write script
        </Button>
        <RelocalizeButton clone={clone} />
      </div>
    </div>
  );
}

function UnchangedCandidate({ asset, clone }: { asset: CloneAsset; clone: FilmCloneDetail }) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (isExpanded) {
    return (
      <li>
        <LocalizedAssetCard asset={asset} clone={clone} onKeepUnchanged={() => setIsExpanded(false)} />
      </li>
    );
  }

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border px-4 py-2">
      <span className="min-w-0 text-sm break-words">
        {asset.name} <span className="text-muted">({ASSET_KIND_LABELS[asset.kind]})</span>
      </span>
      <Button variant="secondary" onClick={() => setIsExpanded(true)}>
        Change this
      </Button>
    </li>
  );
}
