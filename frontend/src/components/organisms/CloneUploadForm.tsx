"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { AiModelLine } from "@/components/molecules/AiModelLine";
import { AutomaticRunFields } from "@/components/molecules/AutomaticRunFields";
import { Captcha, type CaptchaHandle } from "@/components/molecules/Captcha";
import { CloneMaxFramesField } from "@/components/molecules/CloneMaxFramesField";
import { FileDropField } from "@/components/molecules/FileDropField";
import { SelectField } from "@/components/molecules/SelectField";
import { UploadProgress } from "@/components/molecules/UploadProgress";
import { DEFAULT_AUTOMATIC_RUN_CHOICES, DEFAULT_CLONE_MAX_FRAMES } from "@/features/filmClones/constants";
import { useCreateFilmCloneMutation } from "@/features/filmClones/queries";
import type { AutomaticRunChoices } from "@/features/filmClones/types";
import {
  buildFilmCloneDetailPath,
  isValidCloneMaxFrames,
  resolveAutomaticChoices,
} from "@/features/filmClones/utils";
import { ACCEPTED_VIDEO_EXTENSIONS, UPLOAD_LANGUAGE_OPTIONS, type UploadLanguage } from "@/features/jobs/constants";
import { languageChanged, selectUploadLanguage } from "@/features/jobs/uploadPreferencesSlice";
import { AI_STEP_GROUPS_BY_RUN, FILM_CLONE_SETTINGS_TAB } from "@/features/settings/constants";
import { useAiModelStatus } from "@/features/settings/queries";
import { isAiModelBlocked } from "@/features/settings/utils";
import { IS_CAPTCHA_ENABLED } from "@/lib/captcha/captchaWidget";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { FilmCloneMediaLine } from "./FilmCloneMediaLine";
import { PromptPresetSelect } from "./PromptPresetSelect";

export function CloneUploadForm() {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const language = useAppSelector(selectUploadLanguage);
  const createCloneMutation = useCreateFilmCloneMutation();
  const aiModelStatus = useAiModelStatus(AI_STEP_GROUPS_BY_RUN.filmClone);
  const captchaRef = useRef<CaptchaHandle>(null);
  const [selectedFile, setSelectedFile] = useState<File>();
  const [captchaToken, setCaptchaToken] = useState<string>();
  const [presetId, setPresetId] = useState<string>();
  const [maxFramesText, setMaxFramesText] = useState(String(DEFAULT_CLONE_MAX_FRAMES));
  const [automaticRun, setAutomaticRun] = useState<AutomaticRunChoices>(DEFAULT_AUTOMATIC_RUN_CHOICES);
  const [uploadedPercent, setUploadedPercent] = useState(0);

  const isUploading = createCloneMutation.isPending;
  const hasCaptchaPassed = !IS_CAPTCHA_ENABLED || captchaToken !== undefined;
  const maxFrames = Number(maxFramesText);
  const hasValidMaxFrames = isValidCloneMaxFrames(maxFrames);
  const canSubmit =
    selectedFile !== undefined && hasValidMaxFrames && hasCaptchaPassed && !isAiModelBlocked(aiModelStatus) && !isUploading;

  function resetCaptcha() {
    captchaRef.current?.reset();
    setCaptchaToken(undefined);
  }

  function handleFileSelect(file: File) {
    createCloneMutation.reset();
    setSelectedFile(file);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile || !hasValidMaxFrames || !hasCaptchaPassed) return;
    setUploadedPercent(0);
    createCloneMutation.mutate(
      {
        file: selectedFile,
        language,
        presetId,
        maxFrames,
        automaticChoices: resolveAutomaticChoices(automaticRun),
        captchaToken,
        onUploadProgress: setUploadedPercent,
      },
      {
        onSuccess: (clone) => router.push(buildFilmCloneDetailPath(clone.id)),
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
      <CloneMaxFramesField value={maxFramesText} isDisabled={isUploading} onChange={setMaxFramesText} />
      <AutomaticRunFields automaticRun={automaticRun} isDisabled={isUploading} onChange={setAutomaticRun} />
      {aiModelStatus && (
        <AiModelLine
          status={aiModelStatus}
          inputMode={aiModelStatus.filmCloneInputMode}
          inputModeSettingsTab={FILM_CLONE_SETTINGS_TAB}
        />
      )}
      <FilmCloneMediaLine />
      <Captcha ref={captchaRef} onToken={setCaptchaToken} onTokenCleared={() => setCaptchaToken(undefined)} />
      {isUploading && <UploadProgress uploadedPercent={uploadedPercent} />}
      {createCloneMutation.isError && <ErrorAlert>{createCloneMutation.error.message}</ErrorAlert>}
      <Button type="submit" disabled={!canSubmit}>
        Clone
      </Button>
    </form>
  );
}
