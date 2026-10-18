"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { InfoNotice } from "@/components/atoms/InfoNotice";
import { Captcha, type CaptchaHandle } from "@/components/molecules/Captcha";
import { FilmNarrationFields } from "@/components/molecules/FilmNarrationFields";
import { SelectField } from "@/components/molecules/SelectField";
import { TextField } from "@/components/molecules/TextField";
import type { FilmCloneDetail } from "@/features/filmClones/types";
import { aspectToFrameOrientation, labelsToSelectOptions } from "@/features/filmClones/utils";
import {
  ACTIVE_PROJECT_STATUS,
  CLIP_DURATION_OPTIONS,
  DEFAULT_CLIP_LENGTH_HINT,
  FILM_LANGUAGE_LABELS,
  FILM_STUDIO_LANGUAGE_NOTICE,
  NEW_PROJECT_LABEL,
  NEW_PROJECT_VALUE,
  ORIENTATION_LABELS,
  SEND_TO_FILM_STUDIO_LABEL,
} from "@/features/films/constants";
import {
  useCreateFilmEpisodeMutation,
  useCreateFilmProjectMutation,
  useEpisodeActionMutation,
  useFilmProjectsQuery,
  useFilmStylesQuery,
  useFilmVoicesQuery,
} from "@/features/films/queries";
import type { Episode, FilmLanguage, Orientation, ProjectSettingsDraft } from "@/features/films/types";
import {
  buildFilmEpisodePath,
  buildProjectNameFromScriptTitle,
  createDefaultProjectDraft,
  hasNarratorWhenNarrating,
  settingsDraftToFields,
  sortByName,
  stylesToOptions,
  toFilmLanguage,
  voicesToOptions,
} from "@/features/films/utils";
import { IS_CAPTCHA_ENABLED } from "@/lib/captcha/captchaWidget";
import { FilmStudioMediaLine } from "./FilmStudioMediaLine";

const FILM_LANGUAGE_OPTIONS = labelsToSelectOptions(FILM_LANGUAGE_LABELS);
const ORIENTATION_OPTIONS = labelsToSelectOptions(ORIENTATION_LABELS);

interface SendToFilmStudioFormProps {
  clone: FilmCloneDetail;
}

export function SendToFilmStudioForm({ clone }: SendToFilmStudioFormProps) {
  const filmLanguage = toFilmLanguage(clone.scriptLanguage);

  if (filmLanguage === null) {
    return (
      <div className="flex flex-col gap-5">
        <InfoNotice>{FILM_STUDIO_LANGUAGE_NOTICE}</InfoNotice>
        <Button disabled>{SEND_TO_FILM_STUDIO_LABEL}</Button>
      </div>
    );
  }
  return <CloneSendForm clone={clone} filmLanguage={filmLanguage} />;
}

interface CloneSendFormProps {
  clone: FilmCloneDetail;
  filmLanguage: FilmLanguage;
}

function CloneSendForm({ clone, filmLanguage }: CloneSendFormProps) {
  const router = useRouter();
  const projectsQuery = useFilmProjectsQuery(ACTIVE_PROJECT_STATUS);
  const stylesQuery = useFilmStylesQuery();
  const voicesQuery = useFilmVoicesQuery();
  const createProjectMutation = useCreateFilmProjectMutation();
  const createEpisodeMutation = useCreateFilmEpisodeMutation();
  const episodeActionMutation = useEpisodeActionMutation();
  const captchaRef = useRef<CaptchaHandle>(null);
  const [selectedProjectId, setSelectedProjectId] = useState(NEW_PROJECT_VALUE);
  const [draft, setDraft] = useState<ProjectSettingsDraft>(() => ({
    ...createDefaultProjectDraft(filmLanguage),
    name: buildProjectNameFromScriptTitle(clone.scriptTitle),
    orientation: aspectToFrameOrientation(clone.aspect),
  }));
  const [captchaToken, setCaptchaToken] = useState<string>();

  const isNewProject = selectedProjectId === NEW_PROJECT_VALUE;
  const hasCaptchaPassed = !IS_CAPTCHA_ENABLED || captchaToken !== undefined;
  const isBusy = createProjectMutation.isPending || createEpisodeMutation.isPending || episodeActionMutation.isPending;
  const hasProjectInput = !isNewProject || (Boolean(draft.name.trim()) && hasNarratorWhenNarrating(draft));
  const canSubmit = hasProjectInput && hasCaptchaPassed && !isBusy;
  const projectOptions = [
    { value: NEW_PROJECT_VALUE, label: NEW_PROJECT_LABEL },
    ...sortByName(projectsQuery.data ?? []).map((project) => ({ value: project.id, label: project.name })),
  ];
  const mutationError = createProjectMutation.error ?? createEpisodeMutation.error;
  const queryError = projectsQuery.error ?? stylesQuery.error ?? voicesQuery.error;

  function updateDraft(changes: Partial<ProjectSettingsDraft>) {
    setDraft((currentDraft) => ({ ...currentDraft, ...changes }));
  }

  function resetCaptcha() {
    captchaRef.current?.reset();
    setCaptchaToken(undefined);
  }

  function startAndOpenEpisode(projectId: string, episode: Episode) {
    episodeActionMutation.mutate(
      { episodeId: episode.id, action: "start" },
      { onSettled: () => router.push(buildFilmEpisodePath(projectId, episode.number)) },
    );
  }

  function createEpisode(projectId: string) {
    createEpisodeMutation.mutate(
      { projectId, fields: { source: "film_clone", sourceCloneId: clone.id }, captchaToken },
      { onSuccess: (episode) => startAndOpenEpisode(projectId, episode), onSettled: resetCaptcha },
    );
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;
    if (!isNewProject) {
      createEpisode(selectedProjectId);
      return;
    }
    createProjectMutation.mutate(
      { ...settingsDraftToFields(draft), characterIds: [] },
      {
        onSuccess: (project) => {
          setSelectedProjectId(project.id);
          createEpisode(project.id);
        },
        onError: resetCaptcha,
      },
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <SelectField<string>
        label="Project"
        value={selectedProjectId}
        options={projectOptions}
        isDisabled={isBusy}
        onChange={setSelectedProjectId}
      />
      {isNewProject && (
        <>
          <TextField
            label="Project name"
            value={draft.name}
            isDisabled={isBusy}
            onChange={(name) => updateDraft({ name })}
          />
          <SelectField<FilmLanguage>
            label="Language"
            value={draft.language}
            options={FILM_LANGUAGE_OPTIONS}
            isDisabled
            onChange={(language) => updateDraft({ language })}
          />
          <SelectField<Orientation>
            label="Frame"
            value={draft.orientation}
            options={ORIENTATION_OPTIONS}
            isDisabled
            onChange={(orientation) => updateDraft({ orientation })}
          />
          <SelectField<string>
            label="Style"
            value={draft.styleId}
            options={stylesToOptions(stylesQuery.data, draft.styleId)}
            isDisabled={isBusy}
            onChange={(styleId) => updateDraft({ styleId })}
          />
          <SelectField<string>
            label="Default clip length"
            value={draft.clipDurationS}
            options={CLIP_DURATION_OPTIONS}
            hint={DEFAULT_CLIP_LENGTH_HINT}
            isDisabled={isBusy}
            onChange={(clipDurationS) => updateDraft({ clipDurationS })}
          />
          <FilmNarrationFields
            settings={draft}
            voiceOptions={voicesToOptions(voicesQuery.data)}
            isDisabled={isBusy}
            onChange={updateDraft}
          />
        </>
      )}
      <FilmStudioMediaLine />
      <Captcha ref={captchaRef} onToken={setCaptchaToken} onTokenCleared={() => setCaptchaToken(undefined)} />
      {queryError && <ErrorAlert>{queryError.message}</ErrorAlert>}
      {mutationError && <ErrorAlert>{mutationError.message}</ErrorAlert>}
      <Button type="submit" disabled={!canSubmit}>
        {SEND_TO_FILM_STUDIO_LABEL}
      </Button>
    </form>
  );
}
