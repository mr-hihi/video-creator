import type { JobStepState } from "@/features/jobs/types";

const STEP_MARKER_CLASS_NAMES: Record<JobStepState, string> = {
  completed: "border-emerald-500 bg-emerald-500 text-white",
  current: "border-accent bg-accent text-accent-foreground animate-pulse",
  failed: "border-red-500 bg-red-500 text-white",
  upcoming: "border-border bg-surface text-muted",
};

const STEP_LABEL_CLASS_NAMES: Record<JobStepState, string> = {
  completed: "text-foreground",
  current: "font-semibold text-foreground",
  failed: "font-semibold text-red-700 dark:text-red-300",
  upcoming: "text-muted",
};

const STEP_STATE_DESCRIPTIONS: Record<JobStepState, string> = {
  completed: "completed",
  current: "in progress",
  failed: "failed",
  upcoming: "not started",
};

export interface ProgressStep {
  key: string;
  label: string;
  state: JobStepState;
}

interface StepProgressListProps {
  steps: readonly ProgressStep[];
}

export function StepProgressList({ steps }: StepProgressListProps) {
  return (
    <ol className="flex flex-col gap-3">
      {steps.map(({ key, label, state }, stepIndex) => (
        <li key={key} aria-current={state === "current" ? "step" : undefined} className="flex items-center gap-3">
          <span
            className={`flex size-7 shrink-0 items-center justify-center rounded-full border-2 text-xs font-semibold ${STEP_MARKER_CLASS_NAMES[state]}`}
          >
            {stepIndex + 1}
          </span>
          <span className={`text-sm ${STEP_LABEL_CLASS_NAMES[state]}`}>{label}</span>
          <span className="sr-only">({STEP_STATE_DESCRIPTIONS[state]})</span>
        </li>
      ))}
    </ol>
  );
}
