"use client";

import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { Panel } from "@/components/atoms/Panel";
import { SuccessNotice } from "@/components/atoms/SuccessNotice";
import { SavableTextAreaField } from "@/components/molecules/SavableTextAreaField";
import { STORY_BIBLE_HINT, STORY_BIBLE_MAX_LENGTH } from "@/features/films/constants";
import { useUpdateFilmProjectMutation } from "@/features/films/queries";
import type { FilmProjectDetail } from "@/features/films/types";
import {
  describeStoryBibleUpdate,
  describeStoryBibleUpdatingHint,
  findStoryBibleEpisode,
} from "@/features/films/utils";
import { SAVED_NOTICE } from "@/features/settings/constants";

interface FilmStoryBibleFormProps {
  project: FilmProjectDetail;
  isReadOnly: boolean;
}

export function FilmStoryBibleForm({ project, isReadOnly }: FilmStoryBibleFormProps) {
  const updateProjectMutation = useUpdateFilmProjectMutation();
  const updatingEpisode = findStoryBibleEpisode(project.episodes);

  function saveStoryBible(storyBible: string) {
    updateProjectMutation.mutate({ projectId: project.id, changes: { storyBible } });
  }

  return (
    <Panel title="Story bible">
      <div className="flex flex-col gap-4">
        <SavableTextAreaField
          label="Story bible"
          savedValue={project.storyBible ?? ""}
          maxLength={STORY_BIBLE_MAX_LENGTH}
          hint={STORY_BIBLE_HINT}
          isDisabled={isReadOnly || updatingEpisode !== undefined}
          isSaving={updateProjectMutation.isPending}
          onSave={saveStoryBible}
        />
        <p className="text-sm text-muted">{describeStoryBibleUpdate(project, project.episodes)}</p>
        {updatingEpisode && <p className="text-sm text-muted">{describeStoryBibleUpdatingHint(updatingEpisode.number)}</p>}
        {updateProjectMutation.isError && <ErrorAlert>{updateProjectMutation.error.message}</ErrorAlert>}
        {updateProjectMutation.isSuccess && <SuccessNotice>{SAVED_NOTICE}</SuccessNotice>}
      </div>
    </Panel>
  );
}
