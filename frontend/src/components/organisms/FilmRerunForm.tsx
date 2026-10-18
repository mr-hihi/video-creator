"use client";

import { useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { AiModelLine } from "@/components/molecules/AiModelLine";
import { Captcha, type CaptchaHandle } from "@/components/molecules/Captcha";
import { useCreateFilmAnalysisRerunJobMutation } from "@/features/jobs/queries";
import { buildFilmAnalysisDetailPath } from "@/features/jobs/utils";
import { AI_STEP_GROUPS_BY_RUN } from "@/features/settings/constants";
import { useAiModelStatus } from "@/features/settings/queries";
import { isAiModelBlocked } from "@/features/settings/utils";
import { IS_CAPTCHA_ENABLED } from "@/lib/captcha/captchaWidget";
import { PromptPresetSelect } from "./PromptPresetSelect";

interface FilmRerunFormProps {
  sourceJobId: string;
}

export function FilmRerunForm({ sourceJobId }: FilmRerunFormProps) {
  const router = useRouter();
  const rerunMutation = useCreateFilmAnalysisRerunJobMutation();
  const aiModelStatus = useAiModelStatus(AI_STEP_GROUPS_BY_RUN.filmAnalysisRerun);
  const captchaRef = useRef<CaptchaHandle>(null);
  const [presetId, setPresetId] = useState<string>();
  const [captchaToken, setCaptchaToken] = useState<string>();

  const isRerunning = rerunMutation.isPending;
  const hasCaptchaPassed = !IS_CAPTCHA_ENABLED || captchaToken !== undefined;

  function resetCaptcha() {
    captchaRef.current?.reset();
    setCaptchaToken(undefined);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!hasCaptchaPassed) return;
    rerunMutation.mutate(
      { sourceJobId, presetId, captchaToken },
      {
        onSuccess: (job) => router.push(buildFilmAnalysisDetailPath(job.id)),
        onSettled: resetCaptcha,
      },
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <PromptPresetSelect selectedPresetId={presetId} isDisabled={isRerunning} onChange={setPresetId} />
      {aiModelStatus && <AiModelLine status={aiModelStatus} />}
      <Captcha ref={captchaRef} onToken={setCaptchaToken} onTokenCleared={() => setCaptchaToken(undefined)} />
      {rerunMutation.isError && <ErrorAlert>{rerunMutation.error.message}</ErrorAlert>}
      <Button type="submit" disabled={!hasCaptchaPassed || isAiModelBlocked(aiModelStatus) || isRerunning}>
        Rerun
      </Button>
    </form>
  );
}
