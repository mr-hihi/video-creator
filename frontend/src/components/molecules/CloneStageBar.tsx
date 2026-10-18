import type { CloneStageState, FilmClone } from "@/features/filmClones/types";
import { describeFilmCloneStep, determineCloneStages } from "@/features/filmClones/utils";

const STAGE_MARKER_CLASS_NAMES: Record<CloneStageState, string> = {
  completed: "border-emerald-500 bg-emerald-500 text-white",
  current: "border-accent bg-accent text-accent-foreground animate-pulse",
  waiting: "border-accent bg-surface text-accent",
  failed: "border-red-500 bg-red-500 text-white",
  upcoming: "border-border bg-surface text-muted",
};

const STAGE_LABEL_CLASS_NAMES: Record<CloneStageState, string> = {
  completed: "text-foreground",
  current: "font-semibold text-foreground",
  waiting: "font-semibold text-accent",
  failed: "font-semibold text-red-700 dark:text-red-300",
  upcoming: "text-muted",
};

interface CloneStageBarProps {
  clone: Pick<FilmClone, "status" | "step">;
}

export function CloneStageBar({ clone }: CloneStageBarProps) {
  return (
    <div className="flex flex-col gap-2">
      <ol aria-label="Stages" className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {determineCloneStages(clone).map(({ label, state }, stageIndex) => (
          <li
            key={label}
            aria-current={state === "current" ? "step" : undefined}
            className="flex items-center gap-3 rounded-lg border border-border bg-background px-3 py-2"
          >
            <span
              className={`flex size-7 shrink-0 items-center justify-center rounded-full border-2 text-xs font-semibold ${STAGE_MARKER_CLASS_NAMES[state]}`}
            >
              {stageIndex + 1}
            </span>
            <span className="flex min-w-0 flex-col">
              <span className={`text-sm ${STAGE_LABEL_CLASS_NAMES[state]}`}>{label}</span>
              <span className="text-xs text-muted">{state}</span>
            </span>
          </li>
        ))}
      </ol>
      <p aria-live="polite" className="text-sm text-muted">
        {describeFilmCloneStep(clone)}
      </p>
    </div>
  );
}
