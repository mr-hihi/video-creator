"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { AiModelLine } from "@/components/molecules/AiModelLine";
import { AutomaticRunFields } from "@/components/molecules/AutomaticRunFields";
import { Captcha, type CaptchaHandle } from "@/components/molecules/Captcha";
import { CloneMaxFramesField } from "@/components/molecules/CloneMaxFramesField";
import { SelectField } from "@/components/molecules/SelectField";
import { TextField } from "@/components/molecules/TextField";
import { DEFAULT_AUTOMATIC_RUN_CHOICES, DEFAULT_CLONE_MAX_FRAMES } from "@/features/filmClones/constants";
import { useCreateYoutubeFilmCloneMutation } from "@/features/filmClones/queries";
import type { AutomaticRunChoices } from "@/features/filmClones/types";
import {
  buildFilmCloneDetailPath,
  isValidCloneMaxFrames,
  resolveAutomaticChoices,
} from "@/features/filmClones/utils";
import { UPLOAD_LANGUAGE_OPTIONS, YOUTUBE_LINK_PLACEHOLDER, type UploadLanguage } from "@/features/jobs/constants";
import { languageChanged, selectUploadLanguage } from "@/features/jobs/uploadPreferencesSlice";
import { AI_STEP_GROUPS_BY_RUN, FILM_CLONE_SETTINGS_TAB } from "@/features/settings/constants";
import { useAiModelStatus } from "@/features/settings/queries";
import { isAiModelBlocked } from "@/features/settings/utils";
import { IS_CAPTCHA_ENABLED } from "@/lib/captcha/captchaWidget";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { FilmCloneMediaLine } from "./FilmCloneMediaLine";
import { PromptPresetSelect } from "./PromptPresetSelect";

export function CloneYoutubeForm() {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const language = useAppSelector(selectUploadLanguage);
  const createCloneMutation = useCreateYoutubeFilmCloneMutation();
  const aiModelStatus = useAiModelStatus(AI_STEP_GROUPS_BY_RUN.filmClone);
  const captchaRef = useRef<CaptchaHandle>(null);
  const [link, setLink] = useState("");
  const [captchaToken, setCaptchaToken] = useState<string>();
  const [presetId, setPresetId] = useState<string>();
  const [maxFramesText, setMaxFramesText] = useState(String(DEFAULT_CLONE_MAX_FRAMES));
  const [automaticRun, setAutomaticRun] = useState<AutomaticRunChoices>(DEFAULT_AUTOMATIC_RUN_CHOICES);

  const isChecking = createCloneMutation.isPending;
  const trimmedLink = link.trim();
  const hasCaptchaPassed = !IS_CAPTCHA_ENABLED || captchaToken !== undefined;
  const maxFrames = Number(maxFramesText);
  const hasValidMaxFrames = isValidCloneMaxFrames(maxFrames);
  const canSubmit =
    trimmedLink !== "" && hasValidMaxFrames && hasCaptchaPassed && !isAiModelBlocked(aiModelStatus) && !isChecking;

  function resetCaptcha() {
    captchaRef.current?.reset();
    setCaptchaToken(undefined);
  }

  function handleLinkChange(nextLink: string) {
    createCloneMutation.reset();
    setLink(nextLink);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!trimmedLink || !hasValidMaxFrames || !hasCaptchaPassed) return;
    createCloneMutation.mutate(
      {
        url: trimmedLink,
        language,
        presetId,
        maxFrames,
        automaticChoices: resolveAutomaticChoices(automaticRun),
        captchaToken,
      },
      {
        onSuccess: (clone) => router.push(buildFilmCloneDetailPath(clone.id)),
        onSettled: resetCaptcha,
      },
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <TextField
        label="YouTube link"
        value={link}
        placeholder={YOUTUBE_LINK_PLACEHOLDER}
        inputMode="url"
        isDisabled={isChecking}
        onChange={handleLinkChange}
      />
      <SelectField<UploadLanguage>
        label="Caption language"
        value={language}
        options={UPLOAD_LANGUAGE_OPTIONS}
        isDisabled={isChecking}
        onChange={(nextLanguage) => dispatch(languageChanged(nextLanguage))}
      />
      <PromptPresetSelect selectedPresetId={presetId} isDisabled={isChecking} onChange={setPresetId} />
      <CloneMaxFramesField value={maxFramesText} isDisabled={isChecking} onChange={setMaxFramesText} />
      <AutomaticRunFields automaticRun={automaticRun} isDisabled={isChecking} onChange={setAutomaticRun} />
      {aiModelStatus && (
        <AiModelLine
          status={aiModelStatus}
          inputMode={aiModelStatus.filmCloneInputMode}
          inputModeSettingsTab={FILM_CLONE_SETTINGS_TAB}
        />
      )}
      <FilmCloneMediaLine />
      <Captcha ref={captchaRef} onToken={setCaptchaToken} onTokenCleared={() => setCaptchaToken(undefined)} />
      {createCloneMutation.isError && <ErrorAlert>{createCloneMutation.error.message}</ErrorAlert>}
      <Button type="submit" disabled={!canSubmit}>
        {isChecking ? "Checking video…" : "Clone"}
      </Button>
    </form>
  );
}
