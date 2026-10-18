"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { FilmProjectFields } from "@/components/molecules/FilmProjectFields";
import { SearchableCheckboxListField } from "@/components/molecules/SearchableCheckboxListField";
import { EMPTY_VALUE_LABEL, SEARCH_BY_NAME_PLACEHOLDER } from "@/features/films/constants";
import {
  useCreateFilmProjectMutation,
  useFilmCharactersQuery,
  useFilmStylesQuery,
  useFilmVoicesQuery,
} from "@/features/films/queries";
import type { ProjectSettingsDraft } from "@/features/films/types";
import {
  buildFilmProjectPath,
  charactersToOptions,
  chooseFilmLanguage,
  createDefaultProjectDraft,
  settingsDraftToFields,
  stylesToOptions,
  voicesToOptions,
} from "@/features/films/utils";
import { selectUploadLanguage } from "@/features/jobs/uploadPreferencesSlice";
import { useAppSelector } from "@/store/hooks";
import { FilmStudioMediaLine } from "./FilmStudioMediaLine";

interface NewFilmProjectFormProps {
  onCancel: () => void;
}

export function NewFilmProjectForm({ onCancel }: NewFilmProjectFormProps) {
  const router = useRouter();
  const uploadLanguage = useAppSelector(selectUploadLanguage);
  const stylesQuery = useFilmStylesQuery();
  const voicesQuery = useFilmVoicesQuery();
  const charactersQuery = useFilmCharactersQuery();
  const createProjectMutation = useCreateFilmProjectMutation();
  const [draft, setDraft] = useState<ProjectSettingsDraft>(() =>
    createDefaultProjectDraft(chooseFilmLanguage([uploadLanguage])),
  );
  const [characterIds, setCharacterIds] = useState<string[]>([]);

  const isCreating = createProjectMutation.isPending;
  const canCreate = Boolean(draft.name.trim()) && !isCreating;
  const queryError = stylesQuery.error ?? voicesQuery.error ?? charactersQuery.error;

  function updateDraft(changes: Partial<ProjectSettingsDraft>) {
    setDraft((currentDraft) => ({ ...currentDraft, ...changes }));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canCreate) return;
    createProjectMutation.mutate(
      { ...settingsDraftToFields(draft), characterIds },
      { onSuccess: (project) => router.push(buildFilmProjectPath(project.id)) },
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <FilmProjectFields
        draft={draft}
        styleOptions={stylesToOptions(stylesQuery.data, draft.styleId)}
        voiceOptions={voicesToOptions(voicesQuery.data)}
        isLookFixed={false}
        isDisabled={isCreating}
        onChange={updateDraft}
      />
      <SearchableCheckboxListField
        label="Cast"
        searchPlaceholder={SEARCH_BY_NAME_PLACEHOLDER}
        options={charactersToOptions(charactersQuery.data ?? [])}
        selectedValues={characterIds}
        emptyText={EMPTY_VALUE_LABEL}
        isDisabled={isCreating}
        onChange={setCharacterIds}
      />
      <FilmStudioMediaLine />
      {queryError && <ErrorAlert>{queryError.message}</ErrorAlert>}
      {createProjectMutation.isError && <ErrorAlert>{createProjectMutation.error.message}</ErrorAlert>}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={!canCreate}>
          Create
        </Button>
        <Button variant="secondary" disabled={isCreating} onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
