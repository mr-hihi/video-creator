"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { ModalDialog } from "@/components/atoms/ModalDialog";
import { AiModelLine } from "@/components/molecules/AiModelLine";
import { Captcha, type CaptchaHandle } from "@/components/molecules/Captcha";
import { FilmLookFields } from "@/components/molecules/FilmLookFields";
import { NumberField } from "@/components/molecules/NumberField";
import { SelectField } from "@/components/molecules/SelectField";
import { SendToFilmStudioButtons } from "@/components/molecules/SendToFilmStudioButtons";
import { TextAreaField } from "@/components/molecules/TextAreaField";
import { TextField } from "@/components/molecules/TextField";
import {
  ACTIVE_PROJECT_STATUS,
  DEFAULT_TARGET_DURATION_S,
  IDEA_MAX_LENGTH,
  NEW_PROJECT_LABEL,
  NEW_PROJECT_VALUE,
  SEND_TO_FILM_STUDIO_LABEL,
  TARGET_DURATION_LOWER_LIMIT_S,
} from "@/features/films/constants";
import {
  useCreateFilmEpisodeMutation,
  useCreateFilmProjectMutation,
  useEpisodeActionMutation,
  useFilmProjectsQuery,
  useFilmStylesQuery,
} from "@/features/films/queries";
import type { Episode, FilmLookSettings } from "@/features/films/types";
import {
  buildAnalysisProjectFields,
  buildFilmEpisodePath,
  buildProjectNameFromFilename,
  chooseFilmLanguage,
  createDefaultLookSettings,
  isValidTargetDuration,
  sortByName,
  stylesToOptions,
} from "@/features/films/utils";
import { selectUploadLanguage } from "@/features/jobs/uploadPreferencesSlice";
import type { JobDetail } from "@/features/jobs/types";
import { AI_STEP_GROUPS_BY_RUN } from "@/features/settings/constants";
import { useAiModelStatus } from "@/features/settings/queries";
import { isAiModelBlocked } from "@/features/settings/utils";
import { IS_CAPTCHA_ENABLED } from "@/lib/captcha/captchaWidget";
import { useAppSelector } from "@/store/hooks";
import { FilmStudioMediaLine } from "./FilmStudioMediaLine";

interface SendAnalysisToFilmStudioFormProps {
  job: JobDetail;
  onClose: () => void;
}

export function SendAnalysisToFilmStudioForm({ job, onClose }: SendAnalysisToFilmStudioFormProps) {
  const router = useRouter();
  const uploadLanguage = useAppSelector(selectUploadLanguage);
  const projectsQuery = useFilmProjectsQuery(ACTIVE_PROJECT_STATUS);
  const stylesQuery = useFilmStylesQuery();
  const createProjectMutation = useCreateFilmProjectMutation();
  const createEpisodeMutation = useCreateFilmEpisodeMutation();
  const episodeActionMutation = useEpisodeActionMutation();
  const aiModelStatus = useAiModelStatus(AI_STEP_GROUPS_BY_RUN.filmScript);
  const captchaRef = useRef<CaptchaHandle>(null);
  const [selectedProjectId, setSelectedProjectId] = useState(NEW_PROJECT_VALUE);
  const [projectName, setProjectName] = useState(() => buildProjectNameFromFilename(job.sourceFilename));
  const [lookSettings, setLookSettings] = useState<FilmLookSettings>(() =>
    createDefaultLookSettings(chooseFilmLanguage([job.options.language, uploadLanguage])),
  );
  const [targetDurationText, setTargetDurationText] = useState(String(DEFAULT_TARGET_DURATION_S));
  const [extraDirection, setExtraDirection] = useState("");
  const [captchaToken, setCaptchaToken] = useState<string>();

  const isNewProject = selectedProjectId === NEW_PROJECT_VALUE;
  const targetDurationS = Number(targetDurationText);
  const hasCaptchaPassed = !IS_CAPTCHA_ENABLED || captchaToken !== undefined;
  const isBusy = createProjectMutation.isPending || createEpisodeMutation.isPending || episodeActionMutation.isPending;
  const hasProjectInput = !isNewProject || Boolean(projectName.trim());
  const canSubmit =
    hasProjectInput &&
    isValidTargetDuration(targetDurationS) &&
    hasCaptchaPassed &&
    !isAiModelBlocked(aiModelStatus) &&
    !isBusy;
  const projectOptions = [
    { value: NEW_PROJECT_VALUE, label: NEW_PROJECT_LABEL },
    ...sortByName(projectsQuery.data ?? []).map((project) => ({ value: project.id, label: project.name })),
  ];
  const mutationError = createProjectMutation.error ?? createEpisodeMutation.error;
  const queryError = projectsQuery.error ?? stylesQuery.error;

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
      {
        projectId,
        fields: {
          source: "film_analysis",
          sourceJobId: job.id,
          idea: extraDirection.trim() ? extraDirection : undefined,
          targetDurationS,
        },
        captchaToken,
      },
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
    createProjectMutation.mutate(buildAnalysisProjectFields(projectName, lookSettings), {
      onSuccess: (project) => {
        setSelectedProjectId(project.id);
        createEpisode(project.id);
      },
      onError: resetCaptcha,
    });
  }

  return (
    <ModalDialog title={SEND_TO_FILM_STUDIO_LABEL} isClosable={!isBusy} onClose={onClose}>
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
            <TextField label="Project name" value={projectName} isDisabled={isBusy} onChange={setProjectName} />
            <FilmLookFields
              settings={lookSettings}
              styleOptions={stylesToOptions(stylesQuery.data, lookSettings.styleId)}
              isLookFixed={false}
              isDisabled={isBusy}
              onChange={(changes) => setLookSettings((currentSettings) => ({ ...currentSettings, ...changes }))}
            />
          </>
        )}
        <NumberField
          label="Target length"
          value={targetDurationText}
          min={TARGET_DURATION_LOWER_LIMIT_S}
          isDisabled={isBusy}
          onChange={setTargetDurationText}
        />
        <TextAreaField
          label="Extra direction"
          value={extraDirection}
          maxLength={IDEA_MAX_LENGTH}
          isDisabled={isBusy}
          onChange={setExtraDirection}
        />
        {aiModelStatus && <AiModelLine status={aiModelStatus} />}
        <FilmStudioMediaLine />
        <Captcha ref={captchaRef} onToken={setCaptchaToken} onTokenCleared={() => setCaptchaToken(undefined)} />
        {queryError && <ErrorAlert>{queryError.message}</ErrorAlert>}
        {mutationError && <ErrorAlert>{mutationError.message}</ErrorAlert>}
        <SendToFilmStudioButtons canSubmit={canSubmit} isBusy={isBusy} onCancel={onClose} />
      </form>
    </ModalDialog>
  );
}
