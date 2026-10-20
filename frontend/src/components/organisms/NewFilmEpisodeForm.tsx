"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { SegmentedControl } from "@/components/atoms/SegmentedControl";
import { AiModelLine } from "@/components/molecules/AiModelLine";
import { Captcha, type CaptchaHandle } from "@/components/molecules/Captcha";
import { CheckboxField } from "@/components/molecules/CheckboxField";
import { NumberField } from "@/components/molecules/NumberField";
import { SelectField } from "@/components/molecules/SelectField";
import { TextAreaField } from "@/components/molecules/TextAreaField";
import { labelsToSelectOptions } from "@/features/filmClones/utils";
import {
  DEFAULT_EPISODE_SOURCE,
  DEFAULT_STOP_POINTS,
  DEFAULT_SUBTITLE_STYLE,
  DEFAULT_TARGET_DURATION_S,
  EMPTY_VALUE_LABEL,
  EPISODE_SOURCE_OPTIONS,
  EXTRA_DIRECTION_LABEL,
  IDEA_LABEL,
  IDEA_MAX_LENGTH,
  STOP_POINT_FIELDS,
  SUBTITLE_STYLE_LABELS,
  TARGET_DURATION_LOWER_LIMIT_S,
  TARGET_LENGTH_HINT,
  type NewEpisodeSource,
} from "@/features/films/constants";
import { useCreateFilmEpisodeMutation, useEpisodeActionMutation } from "@/features/films/queries";
import type { CreateEpisodeFields, Episode, FilmProjectDetail, StopPoints, SubtitleStyle } from "@/features/films/types";
import {
  buildFilmEpisodePath,
  doneAnalysesToOptions,
  isValidTargetDuration,
} from "@/features/films/utils";
import { FILM_ANALYSIS_JOB_TYPES } from "@/features/jobs/constants";
import { useJobsQuery } from "@/features/jobs/queries";
import { useAiModelStatus } from "@/features/settings/queries";
import { isAiModelBlocked } from "@/features/settings/utils";
import { IS_CAPTCHA_ENABLED } from "@/lib/captcha/captchaWidget";
import { PromptPresetSelect } from "./PromptPresetSelect";

const SUBTITLE_STYLE_OPTIONS = labelsToSelectOptions(SUBTITLE_STYLE_LABELS);
const NO_ANALYSIS_OPTION = { value: "", label: EMPTY_VALUE_LABEL };

interface NewFilmEpisodeFormProps {
  project: FilmProjectDetail;
  isReadOnly: boolean;
}

export function NewFilmEpisodeForm({ project, isReadOnly }: NewFilmEpisodeFormProps) {
  const router = useRouter();
  const analysesQuery = useJobsQuery(FILM_ANALYSIS_JOB_TYPES);
  const createEpisodeMutation = useCreateFilmEpisodeMutation();
  const episodeActionMutation = useEpisodeActionMutation();
  const aiModelStatus = useAiModelStatus({ kind: "filmScript" });
  const captchaRef = useRef<CaptchaHandle>(null);
  const [source, setSource] = useState<NewEpisodeSource>(DEFAULT_EPISODE_SOURCE);
  const [ideaText, setIdeaText] = useState("");
  const [selectedJobId, setSelectedJobId] = useState<string>();
  const [targetDurationText, setTargetDurationText] = useState(String(DEFAULT_TARGET_DURATION_S));
  const [stopPoints, setStopPoints] = useState<StopPoints>(DEFAULT_STOP_POINTS);
  const [burnSubtitles, setBurnSubtitles] = useState(false);
  const [subtitleStyle, setSubtitleStyle] = useState<SubtitleStyle>(DEFAULT_SUBTITLE_STYLE);
  const [presetId, setPresetId] = useState<string>();
  const [captchaToken, setCaptchaToken] = useState<string>();

  const analysisOptions = doneAnalysesToOptions(analysesQuery.data ?? []);
  const shownJobId = selectedJobId ?? analysisOptions.at(0)?.value;
  const targetDurationS = Number(targetDurationText);
  const hasValidTarget = isValidTargetDuration(targetDurationS);
  const hasSourceInput = source === "idea" ? Boolean(ideaText.trim()) : shownJobId !== undefined;
  const hasCaptchaPassed = !IS_CAPTCHA_ENABLED || captchaToken !== undefined;
  const isBusy = createEpisodeMutation.isPending || episodeActionMutation.isPending;
  const canSubmit =
    !isReadOnly && hasSourceInput && hasValidTarget && hasCaptchaPassed && !isAiModelBlocked(aiModelStatus) && !isBusy;
  const isLocked = isReadOnly || isBusy;

  function resetCaptcha() {
    captchaRef.current?.reset();
    setCaptchaToken(undefined);
  }

  function buildEpisodeFields(): CreateEpisodeFields {
    return {
      source,
      idea: ideaText.trim() ? ideaText : undefined,
      sourceJobId: source === "film_analysis" ? shownJobId : undefined,
      targetDurationS,
      stopPoints,
      burnSubtitles,
      subtitleStyle,
      presetId,
    };
  }

  function openEpisode(episode: Episode, shouldStart: boolean) {
    const episodePath = buildFilmEpisodePath(project.id, episode.number);
    if (!shouldStart) {
      router.push(episodePath);
      return;
    }
    episodeActionMutation.mutate(
      { episodeId: episode.id, action: "start" },
      { onSettled: () => router.push(episodePath) },
    );
  }

  function createEpisode(shouldStart: boolean) {
    if (!canSubmit) return;
    createEpisodeMutation.mutate(
      { projectId: project.id, fields: buildEpisodeFields(), captchaToken },
      { onSuccess: (episode) => openEpisode(episode, shouldStart), onSettled: resetCaptcha },
    );
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createEpisode(true);
  }

  function toggleStopPoint(key: keyof StopPoints, isChecked: boolean) {
    setStopPoints((currentStopPoints) => ({ ...currentStopPoints, [key]: isChecked }));
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <SegmentedControl<NewEpisodeSource>
        label="Source"
        value={source}
        options={EPISODE_SOURCE_OPTIONS}
        isDisabled={isLocked}
        onChange={setSource}
      />
      {source === "film_analysis" && (
        <SelectField<string>
          label="Film analysis"
          value={shownJobId ?? NO_ANALYSIS_OPTION.value}
          options={analysisOptions.length ? analysisOptions : [NO_ANALYSIS_OPTION]}
          isDisabled={isLocked || !analysisOptions.length}
          onChange={setSelectedJobId}
        />
      )}
      <TextAreaField
        label={source === "idea" ? IDEA_LABEL : EXTRA_DIRECTION_LABEL}
        value={ideaText}
        maxLength={IDEA_MAX_LENGTH}
        isDisabled={isLocked}
        onChange={setIdeaText}
      />
      <NumberField
        label="Target length"
        value={targetDurationText}
        min={TARGET_DURATION_LOWER_LIMIT_S}
        hint={TARGET_LENGTH_HINT}
        isDisabled={isLocked}
        onChange={setTargetDurationText}
      />
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-sm font-medium">Pause after</legend>
        {STOP_POINT_FIELDS.map(({ key, label }) => (
          <CheckboxField
            key={key}
            label={label}
            isChecked={stopPoints[key]}
            isDisabled={isLocked}
            onChange={(isChecked) => toggleStopPoint(key, isChecked)}
          />
        ))}
      </fieldset>
      <fieldset className="flex flex-col gap-3">
        <legend className="mb-2 text-sm font-medium">Subtitles</legend>
        <CheckboxField
          label="Burn subtitles into the video"
          isChecked={burnSubtitles}
          isDisabled={isLocked}
          onChange={setBurnSubtitles}
        />
        <SelectField<SubtitleStyle>
          label="Subtitle style"
          value={subtitleStyle}
          options={SUBTITLE_STYLE_OPTIONS}
          isDisabled={isLocked}
          onChange={setSubtitleStyle}
        />
      </fieldset>
      <PromptPresetSelect selectedPresetId={presetId} isDisabled={isLocked} onChange={setPresetId} />
      {aiModelStatus && <AiModelLine status={aiModelStatus} />}
      <Captcha ref={captchaRef} onToken={setCaptchaToken} onTokenCleared={() => setCaptchaToken(undefined)} />
      {analysesQuery.isError && <ErrorAlert>{analysesQuery.error.message}</ErrorAlert>}
      {createEpisodeMutation.isError && <ErrorAlert>{createEpisodeMutation.error.message}</ErrorAlert>}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={!canSubmit}>
          Create and start
        </Button>
        <Button variant="secondary" disabled={!canSubmit} onClick={() => createEpisode(false)}>
          Create
        </Button>
      </div>
    </form>
  );
}
