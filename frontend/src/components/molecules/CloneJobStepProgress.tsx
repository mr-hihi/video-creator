import { JOB_STEP_LABELS } from "@/features/jobs/constants";
import type { CloneJob } from "@/features/filmClones/types";
import { determineCloneJobStepState, listCloneJobSteps } from "@/features/filmClones/utils";
import { StepProgressList } from "./StepProgressList";

interface CloneJobStepProgressProps {
  job: Pick<CloneJob, "type" | "status" | "step" | "options">;
}

export function CloneJobStepProgress({ job }: CloneJobStepProgressProps) {
  const steps = listCloneJobSteps(job).map((step) => ({
    key: step,
    label: JOB_STEP_LABELS[step],
    state: determineCloneJobStepState(job, step),
  }));
  return <StepProgressList steps={steps} />;
}
