import { JOB_STEP_LABELS } from "@/features/jobs/constants";
import type { Job } from "@/features/jobs/types";
import { determineJobStepState, listJobSteps } from "@/features/jobs/utils";
import { StepProgressList } from "./StepProgressList";

interface JobStepProgressProps {
  job: Pick<Job, "type" | "status" | "step" | "options">;
}

export function JobStepProgress({ job }: JobStepProgressProps) {
  const steps = listJobSteps(job).map((step) => ({
    key: step,
    label: JOB_STEP_LABELS[step],
    state: determineJobStepState(job, step),
  }));
  return <StepProgressList steps={steps} />;
}
