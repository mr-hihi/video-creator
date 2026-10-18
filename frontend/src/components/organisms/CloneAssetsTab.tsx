"use client";

import { useState } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { CloneAssetComparison } from "@/components/molecules/CloneAssetComparison";
import { CloneAssetOriginal } from "@/components/molecules/CloneAssetOriginal";
import { ASSET_KIND_GROUPS, EMPTY_VALUE_LABEL } from "@/features/filmClones/constants";
import { useDeleteCloneAssetMutation } from "@/features/filmClones/queries";
import type { CloneAsset, CloneImageOrientation, FilmCloneDetail } from "@/features/filmClones/types";
import { aspectToFrameOrientation, buildDeleteAssetConfirmation, isCloneWaitingAt } from "@/features/filmClones/utils";
import { CloneAssetEditForm } from "./CloneAssetEditForm";

interface CloneAssetsTabProps {
  clone: FilmCloneDetail;
}

export function CloneAssetsTab({ clone }: CloneAssetsTabProps) {
  const deleteAssetMutation = useDeleteCloneAssetMutation();
  const isEditable = isCloneWaitingAt(clone, "choosing_localization");
  const frameOrientation = aspectToFrameOrientation(clone.aspect);

  function handleDelete(asset: CloneAsset) {
    if (!window.confirm(buildDeleteAssetConfirmation(asset.name))) return;
    deleteAssetMutation.mutate(asset.id);
  }

  return (
    <div className="flex flex-col gap-6">
      {deleteAssetMutation.isError && <ErrorAlert>{deleteAssetMutation.error.message}</ErrorAlert>}
      {ASSET_KIND_GROUPS.map(({ kind, title }) => {
        const groupAssets = clone.assets.filter((asset) => asset.kind === kind);
        return (
          <section key={kind} className="flex flex-col gap-3">
            <h3 className="text-base font-semibold">{title}</h3>
            {groupAssets.length ? (
              <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {groupAssets.map((asset) => (
                  <CloneAssetItem
                    key={asset.id}
                    asset={asset}
                    jobId={clone.jobId}
                    frameOrientation={frameOrientation}
                    isEditable={isEditable}
                    isDeleting={deleteAssetMutation.isPending}
                    onDelete={handleDelete}
                  />
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted">{EMPTY_VALUE_LABEL}</p>
            )}
          </section>
        );
      })}
    </div>
  );
}

interface CloneAssetItemProps {
  asset: CloneAsset;
  jobId: string;
  frameOrientation: CloneImageOrientation;
  isEditable: boolean;
  isDeleting: boolean;
  onDelete: (asset: CloneAsset) => void;
}

function CloneAssetItem({ asset, jobId, frameOrientation, isEditable, isDeleting, onDelete }: CloneAssetItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const cardClassName = "flex min-w-0 flex-col gap-3 rounded-lg border border-border p-4";

  if (isEditable && isEditing) {
    return (
      <li className={cardClassName}>
        <CloneAssetEditForm asset={asset} onClose={() => setIsEditing(false)} />
      </li>
    );
  }

  return (
    <li className={`${cardClassName} ${asset.changed ? "sm:col-span-2" : ""}`}>
      {asset.changed ? (
        <CloneAssetComparison asset={asset} jobId={jobId} frameOrientation={frameOrientation} />
      ) : (
        <CloneAssetOriginal asset={asset} jobId={jobId} frameOrientation={frameOrientation} />
      )}
      {isEditable && (
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => setIsEditing(true)}>
            Edit
          </Button>
          <Button variant="secondary" disabled={isDeleting} onClick={() => onDelete(asset)}>
            Delete
          </Button>
        </div>
      )}
    </li>
  );
}
