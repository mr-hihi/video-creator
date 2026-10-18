"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { SelectField } from "@/components/molecules/SelectField";
import { TextAreaField } from "@/components/molecules/TextAreaField";
import { TextField } from "@/components/molecules/TextField";
import { ASSET_KIND_LABELS, DESCRIPTION_MAX_LENGTH } from "@/features/filmClones/constants";
import { useUpdateCloneAssetMutation } from "@/features/filmClones/queries";
import type { AssetKind, CloneAsset, OriginalAssetChanges } from "@/features/filmClones/types";
import { assetToOriginalDraft, haveSameFieldValues, labelsToSelectOptions } from "@/features/filmClones/utils";

const ASSET_KIND_OPTIONS = labelsToSelectOptions(ASSET_KIND_LABELS);

interface CloneAssetEditFormProps {
  asset: CloneAsset;
  onClose: () => void;
}

export function CloneAssetEditForm({ asset, onClose }: CloneAssetEditFormProps) {
  const updateAssetMutation = useUpdateCloneAssetMutation();
  const [draft, setDraft] = useState<OriginalAssetChanges>(() => assetToOriginalDraft(asset));

  const isSaving = updateAssetMutation.isPending;
  const hasChanges = !haveSameFieldValues(draft, assetToOriginalDraft(asset));

  function updateDraft<TField extends keyof OriginalAssetChanges>(field: TField, value: OriginalAssetChanges[TField]) {
    setDraft((currentDraft) => ({ ...currentDraft, [field]: value }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    updateAssetMutation.mutate({ assetId: asset.id, changes: draft }, { onSuccess: onClose });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <TextField label="Name" value={draft.name} isDisabled={isSaving} onChange={(name) => updateDraft("name", name)} />
      <SelectField<AssetKind>
        label="Kind"
        value={draft.kind}
        options={ASSET_KIND_OPTIONS}
        isDisabled={isSaving}
        onChange={(kind) => updateDraft("kind", kind)}
      />
      <TextField
        label="Culture"
        value={draft.culture}
        isDisabled={isSaving}
        onChange={(culture) => updateDraft("culture", culture)}
      />
      <TextField
        label="Period"
        value={draft.period}
        isDisabled={isSaving}
        onChange={(period) => updateDraft("period", period)}
      />
      <TextAreaField
        label="Description"
        value={draft.description}
        maxLength={DESCRIPTION_MAX_LENGTH}
        isDisabled={isSaving}
        onChange={(description) => updateDraft("description", description)}
      />
      {updateAssetMutation.isError && <ErrorAlert>{updateAssetMutation.error.message}</ErrorAlert>}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={!hasChanges || isSaving}>
          Save
        </Button>
        <Button variant="secondary" disabled={isSaving} onClick={onClose}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
