"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { AiModelLine } from "@/components/molecules/AiModelLine";
import { Captcha, type CaptchaHandle } from "@/components/molecules/Captcha";
import { SelectField } from "@/components/molecules/SelectField";
import { TextField } from "@/components/molecules/TextField";
import { UPLOAD_LANGUAGE_OPTIONS, YOUTUBE_LINK_PLACEHOLDER, type UploadLanguage } from "@/features/jobs/constants";
import { useCreateYoutubeToMarkdownJobMutation } from "@/features/jobs/queries";
import { languageChanged, selectUploadLanguage } from "@/features/jobs/uploadPreferencesSlice";
import { buildJobDetailPath } from "@/features/jobs/utils";
import { AI_STEP_GROUPS_BY_RUN } from "@/features/settings/constants";
import { useAiModelStatus } from "@/features/settings/queries";
import { isAiModelBlocked } from "@/features/settings/utils";
import { IS_CAPTCHA_ENABLED } from "@/lib/captcha/captchaWidget";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { PromptPresetSelect } from "./PromptPresetSelect";

export function YoutubeLinkForm() {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const language = useAppSelector(selectUploadLanguage);
  const createJobMutation = useCreateYoutubeToMarkdownJobMutation();
  const aiModelStatus = useAiModelStatus(AI_STEP_GROUPS_BY_RUN.videoToMarkdown);
  const captchaRef = useRef<CaptchaHandle>(null);
  const [link, setLink] = useState("");
  const [captchaToken, setCaptchaToken] = useState<string>();
  const [presetId, setPresetId] = useState<string>();

  const isChecking = createJobMutation.isPending;
  const trimmedLink = link.trim();
  const hasCaptchaPassed = !IS_CAPTCHA_ENABLED || captchaToken !== undefined;
  const canSubmit = trimmedLink !== "" && hasCaptchaPassed && !isAiModelBlocked(aiModelStatus) && !isChecking;

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
    if (!trimmedLink || !hasCaptchaPassed) return;
    createJobMutation.mutate(
      { url: trimmedLink, language, presetId, captchaToken },
      {
        onSuccess: (job) => router.push(buildJobDetailPath(job.id)),
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
      {aiModelStatus && <AiModelLine status={aiModelStatus} inputMode={aiModelStatus.inputMode} />}
      <Captcha ref={captchaRef} onToken={setCaptchaToken} onTokenCleared={() => setCaptchaToken(undefined)} />
      {createJobMutation.isError && <ErrorAlert>{createJobMutation.error.message}</ErrorAlert>}
      <Button type="submit" disabled={!canSubmit}>
        {isChecking ? "Checking video…" : "Convert"}
      </Button>
    </form>
  );
}
