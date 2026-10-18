"use client";

import { useState } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { CloneAssetOriginal } from "@/components/molecules/CloneAssetOriginal";
import { GeneratedImageView } from "@/components/molecules/GeneratedImageView";
import { TextAreaField } from "@/components/molecules/TextAreaField";
import { TextField } from "@/components/molecules/TextField";
import { DESCRIPTION_MAX_LENGTH } from "@/features/filmClones/constants";
import { useGenerateAssetReferenceMutation, useUpdateCloneAssetMutation } from "@/features/filmClones/queries";
import type { CloneAsset, FilmCloneDetail, LocalizedAssetDraft } from "@/features/filmClones/types";
import {
  aspectToFrameOrientation,
  assetToLocalizedDraft,
  buildLocalizedAssetChanges,
  describeAssetName,
  describeGenerateAction,
  haveSameFieldValues,
  isAssetGenerating,
  kindToReferenceOrientation,
} from "@/features/filmClones/utils";

interface LocalizedAssetCardProps {
  asset: CloneAsset;
  clone: FilmCloneDetail;
  onKeepUnchanged?: () => void;
}

export function LocalizedAssetCard({ asset, clone, onKeepUnchanged }: LocalizedAssetCardProps) {
  const updateAssetMutation = useUpdateCloneAssetMutation();
  const generateReferenceMutation = useGenerateAssetReferenceMutation();
  const [draft, setDraft] = useState<LocalizedAssetDraft>(() => assetToLocalizedDraft(asset));

  const isBusy =
    isAssetGenerating(asset, clone.generationRequests) ||
    updateAssetMutation.isPending ||
    generateReferenceMutation.isPending;
  const hasChanges = !haveSameFieldValues(draft, assetToLocalizedDraft(asset));
  const mutationError = updateAssetMutation.error ?? generateReferenceMutation.error;

  function handleSave() {
    updateAssetMutation.mutate(
      { assetId: asset.id, changes: buildLocalizedAssetChanges(draft, asset) },
      { onSuccess: (savedAsset) => setDraft(assetToLocalizedDraft(savedAsset)) },
    );
  }

  function handleKeepOriginal() {
    if (!asset.changed) {
      onKeepUnchanged?.();
      return;
    }
    updateAssetMutation.mutate({ assetId: asset.id, changes: { changed: false } });
  }

  return (
    <article className="grid gap-4 rounded-lg border border-border p-4 md:grid-cols-2">
      <CloneAssetOriginal asset={asset} jobId={clone.jobId} frameOrientation={aspectToFrameOrientation(clone.aspect)} />
      <div className="flex min-w-0 flex-col gap-3">
        <TextField
          label="Localized name"
          value={draft.localizedName}
          isDisabled={isBusy}
          onChange={(localizedName) => setDraft((currentDraft) => ({ ...currentDraft, localizedName }))}
        />
        <TextAreaField
          label="Localized description"
          value={draft.localizedDescription}
          maxLength={DESCRIPTION_MAX_LENGTH}
          isDisabled={isBusy}
          onChange={(localizedDescription) => setDraft((currentDraft) => ({ ...currentDraft, localizedDescription }))}
        />
        <div className="self-start">
          <Button disabled={!hasChanges || isBusy} onClick={handleSave}>
            Save
          </Button>
        </div>
        {asset.localizationNote && <p className="text-xs break-words text-muted">{asset.localizationNote}</p>}
        {asset.changed && (
          <GeneratedImageView
            status={asset.referenceStatus}
            path={asset.referencePath}
            error={asset.referenceError}
            alt={describeAssetName(asset)}
            orientation={kindToReferenceOrientation(asset.kind)}
          />
        )}
        <div className="flex flex-wrap gap-2">
          {asset.changed && (
            <Button
              variant="secondary"
              disabled={isBusy}
              onClick={() => generateReferenceMutation.mutate(asset.id)}
            >
              {describeGenerateAction(asset.referenceStatus)}
            </Button>
          )}
          <Button variant="secondary" disabled={isBusy} onClick={handleKeepOriginal}>
            Keep original
          </Button>
        </div>
        {mutationError && <ErrorAlert>{mutationError.message}</ErrorAlert>}
      </div>
    </article>
  );
}
