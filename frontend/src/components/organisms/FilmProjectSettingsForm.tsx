"use client";

import { useState } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { SuccessNotice } from "@/components/atoms/SuccessNotice";
import { FilmProjectFields } from "@/components/molecules/FilmProjectFields";
import { useFilmStylesQuery, useFilmVoicesQuery, useUpdateFilmProjectMutation } from "@/features/films/queries";
import type { FilmProjectDetail, ProjectSettingsDraft } from "@/features/films/types";
import {
  hasChangedFields,
  pickChangedFields,
  projectToSettingsDraft,
  settingsDraftToFields,
  stylesToOptions,
  voicesToOptions,
} from "@/features/films/utils";
import { SAVED_NOTICE } from "@/features/settings/constants";
import { FilmStudioMediaLine } from "./FilmStudioMediaLine";

interface FilmProjectSettingsFormProps {
  project: FilmProjectDetail;
  isReadOnly: boolean;
}

export function FilmProjectSettingsForm({ project, isReadOnly }: FilmProjectSettingsFormProps) {
  const stylesQuery = useFilmStylesQuery();
  const voicesQuery = useFilmVoicesQuery();
  const updateProjectMutation = useUpdateFilmProjectMutation();
  const [draft, setDraft] = useState<ProjectSettingsDraft>();
  const [notice, setNotice] = useState<string>();

  const savedDraft = projectToSettingsDraft(project);
  const shownDraft = draft ?? savedDraft;
  const changes = pickChangedFields(settingsDraftToFields(shownDraft), settingsDraftToFields(savedDraft));
  const isSaving = updateProjectMutation.isPending;
  const queryError = stylesQuery.error ?? voicesQuery.error;

  function updateDraft(draftChanges: Partial<ProjectSettingsDraft>) {
    setDraft({ ...shownDraft, ...draftChanges });
    setNotice(undefined);
  }

  function handleSave() {
    updateProjectMutation.mutate(
      { projectId: project.id, changes },
      {
        onSuccess: () => {
          setDraft(undefined);
          setNotice(SAVED_NOTICE);
        },
      },
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <FilmProjectFields
        draft={shownDraft}
        styleOptions={stylesToOptions(stylesQuery.data, shownDraft.styleId)}
        voiceOptions={voicesToOptions(voicesQuery.data)}
        isLookFixed={project.isLookFixed}
        isDisabled={isReadOnly || isSaving}
        onChange={updateDraft}
      />
      <FilmStudioMediaLine />
      {queryError && <ErrorAlert>{queryError.message}</ErrorAlert>}
      {updateProjectMutation.isError && <ErrorAlert>{updateProjectMutation.error.message}</ErrorAlert>}
      {notice && <SuccessNotice>{notice}</SuccessNotice>}
      <div className="self-start">
        <Button disabled={isReadOnly || isSaving || !hasChangedFields(changes)} onClick={handleSave}>
          Save
        </Button>
      </div>
    </div>
  );
}
