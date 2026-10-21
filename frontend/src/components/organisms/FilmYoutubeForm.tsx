"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { AiModelLine } from "@/components/molecules/AiModelLine";
import { Captcha, type CaptchaHandle } from "@/components/molecules/Captcha";
import { MaxFramesField } from "@/components/molecules/MaxFramesField";
import { SelectField } from "@/components/molecules/SelectField";
import { TextField } from "@/components/molecules/TextField";
import {
  DEFAULT_MAX_FRAMES,
  UPLOAD_LANGUAGE_OPTIONS,
  YOUTUBE_LINK_PLACEHOLDER,
  type UploadLanguage,
} from "@/features/jobs/constants";
import { useCreateYoutubeFilmAnalysisJobMutation } from "@/features/jobs/queries";
import { languageChanged, selectUploadLanguage } from "@/features/jobs/uploadPreferencesSlice";
import { buildFilmAnalysisDetailPath, isValidMaxFrames } from "@/features/jobs/utils";
import { FILM_ANALYSIS_SETTINGS_TAB } from "@/features/settings/constants";
import { useAiModelStatus } from "@/features/settings/queries";
import { isAiModelBlocked, isFullVideoInputMode } from "@/features/settings/utils";
import { IS_CAPTCHA_ENABLED } from "@/lib/captcha/captchaWidget";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { PromptPresetSelect } from "./PromptPresetSelect";

export function FilmYoutubeForm() {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const language = useAppSelector(selectUploadLanguage);
  const createJobMutation = useCreateYoutubeFilmAnalysisJobMutation();
  const aiModelStatus = useAiModelStatus({ kind: "filmAnalysis" });
  const captchaRef = useRef<CaptchaHandle>(null);
  const [link, setLink] = useState("");
  const [captchaToken, setCaptchaToken] = useState<string>();
  const [presetId, setPresetId] = useState<string>();
  const [maxFramesText, setMaxFramesText] = useState(String(DEFAULT_MAX_FRAMES));

  const isChecking = createJobMutation.isPending;
  const trimmedLink = link.trim();
  const hasCaptchaPassed = !IS_CAPTCHA_ENABLED || captchaToken !== undefined;
  const isMaxFramesShown = !isFullVideoInputMode(aiModelStatus?.inputMode);
  const maxFrames = isMaxFramesShown ? Number(maxFramesText) : undefined;
  const hasValidMaxFrames = maxFrames === undefined || isValidMaxFrames(maxFrames);
  const canSubmit =
    trimmedLink !== "" && hasValidMaxFrames && hasCaptchaPassed && !isAiModelBlocked(aiModelStatus) && !isChecking;

  function resetCaptcha() {
    captchaRef.current?.reset();
    setCaptchaToken(undefined);
  }

  function handleLinkChange(nextLink: string) {
    createJobMutation.reset();
    setLink(nextLink);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!trimmedLink || !hasValidMaxFrames || !hasCaptchaPassed) return;
    createJobMutation.mutate(
      { url: trimmedLink, language, presetId, maxFrames, captchaToken },
      {
        onSuccess: (job) => router.push(buildFilmAnalysisDetailPath(job.id)),
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
      {isMaxFramesShown && (
        <MaxFramesField value={maxFramesText} isDisabled={isChecking} onChange={setMaxFramesText} />
      )}
      {aiModelStatus && <AiModelLine status={aiModelStatus} inputModeSettingsTab={FILM_ANALYSIS_SETTINGS_TAB} />}
      <Captcha ref={captchaRef} onToken={setCaptchaToken} onTokenCleared={() => setCaptchaToken(undefined)} />
      {createJobMutation.isError && <ErrorAlert>{createJobMutation.error.message}</ErrorAlert>}
      <Button type="submit" disabled={!canSubmit}>
        {isChecking ? "Checking video…" : "Analyze"}
      </Button>
    </form>
  );
}
