"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { AiModelLine } from "@/components/molecules/AiModelLine";
import { Captcha, type CaptchaHandle } from "@/components/molecules/Captcha";
import { FileDropField } from "@/components/molecules/FileDropField";
import { MaxFramesField } from "@/components/molecules/MaxFramesField";
import { SelectField } from "@/components/molecules/SelectField";
import { UploadProgress } from "@/components/molecules/UploadProgress";
import {
  ACCEPTED_VIDEO_EXTENSIONS,
  DEFAULT_MAX_FRAMES,
  UPLOAD_LANGUAGE_OPTIONS,
  type UploadLanguage,
} from "@/features/jobs/constants";
import { useCreateFilmAnalysisJobMutation } from "@/features/jobs/queries";
import { languageChanged, selectUploadLanguage } from "@/features/jobs/uploadPreferencesSlice";
import { buildFilmAnalysisDetailPath, isValidMaxFrames } from "@/features/jobs/utils";
import { AI_STEP_GROUPS_BY_RUN } from "@/features/settings/constants";
import { useAiModelStatus } from "@/features/settings/queries";
import { isAiModelBlocked } from "@/features/settings/utils";
import { IS_CAPTCHA_ENABLED } from "@/lib/captcha/captchaWidget";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { PromptPresetSelect } from "./PromptPresetSelect";

export function FilmUploadForm() {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const language = useAppSelector(selectUploadLanguage);
  const createJobMutation = useCreateFilmAnalysisJobMutation();
  const aiModelStatus = useAiModelStatus(AI_STEP_GROUPS_BY_RUN.filmAnalysis);
  const captchaRef = useRef<CaptchaHandle>(null);
  const [selectedFile, setSelectedFile] = useState<File>();
  const [captchaToken, setCaptchaToken] = useState<string>();
  const [presetId, setPresetId] = useState<string>();
  const [maxFramesText, setMaxFramesText] = useState(String(DEFAULT_MAX_FRAMES));
  const [uploadedPercent, setUploadedPercent] = useState(0);

  const isUploading = createJobMutation.isPending;
  const hasCaptchaPassed = !IS_CAPTCHA_ENABLED || captchaToken !== undefined;
  const maxFrames = Number(maxFramesText);
  const hasValidMaxFrames = isValidMaxFrames(maxFrames);
  const canSubmit =
    selectedFile !== undefined && hasValidMaxFrames && hasCaptchaPassed && !isAiModelBlocked(aiModelStatus) && !isUploading;

  function resetCaptcha() {
    captchaRef.current?.reset();
    setCaptchaToken(undefined);
  }

  function handleFileSelect(file: File) {
    createJobMutation.reset();
    setSelectedFile(file);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile || !hasValidMaxFrames || !hasCaptchaPassed) return;
    setUploadedPercent(0);
    createJobMutation.mutate(
      { file: selectedFile, language, presetId, maxFrames, captchaToken, onUploadProgress: setUploadedPercent },
      {
        onSuccess: (job) => router.push(buildFilmAnalysisDetailPath(job.id)),
        onSettled: resetCaptcha,
      },
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <FileDropField
        label="Film"
        acceptedExtensions={ACCEPTED_VIDEO_EXTENSIONS}
        selectedFile={selectedFile}
        isDisabled={isUploading}
        onFileSelect={handleFileSelect}
      />
      <SelectField<UploadLanguage>
        label="Spoken language"
        value={language}
        options={UPLOAD_LANGUAGE_OPTIONS}
        isDisabled={isUploading}
        onChange={(nextLanguage) => dispatch(languageChanged(nextLanguage))}
      />
      <PromptPresetSelect selectedPresetId={presetId} isDisabled={isUploading} onChange={setPresetId} />
      <MaxFramesField value={maxFramesText} isDisabled={isUploading} onChange={setMaxFramesText} />
      {aiModelStatus && <AiModelLine status={aiModelStatus} inputMode={aiModelStatus.inputMode} />}
      <Captcha ref={captchaRef} onToken={setCaptchaToken} onTokenCleared={() => setCaptchaToken(undefined)} />
      {isUploading && <UploadProgress uploadedPercent={uploadedPercent} />}
      {createJobMutation.isError && <ErrorAlert>{createJobMutation.error.message}</ErrorAlert>}
      <Button type="submit" disabled={!canSubmit}>
        Analyze
      </Button>
    </form>
  );
}
