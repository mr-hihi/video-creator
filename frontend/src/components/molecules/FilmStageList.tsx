import type { EpisodeDetail, StageState } from "@/features/films/types";
import { buildEpisodeStages } from "@/features/films/utils";

const STAGE_MARKER_CLASS_NAMES: Record<StageState, string> = {
  completed: "border-emerald-500 bg-emerald-500 text-white",
  current: "border-accent bg-accent text-accent-foreground animate-pulse",
  paused: "border-accent bg-surface text-accent",
  failed: "border-red-500 bg-red-500 text-white",
  upcoming: "border-border bg-surface text-muted",
};

const STAGE_LABEL_CLASS_NAMES: Record<StageState, string> = {
  completed: "text-foreground",
  current: "font-semibold text-foreground",
  paused: "font-semibold text-accent",
  failed: "font-semibold text-red-700 dark:text-red-300",
  upcoming: "text-muted",
};

interface FilmStageListProps {
  episode: Pick<EpisodeDetail, "status" | "step" | "parts">;
}

export function FilmStageList({ episode }: FilmStageListProps) {
  return (
    <ol aria-label="Stages" className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {buildEpisodeStages(episode).map(({ step, label, state, progressLabel }, stageIndex) => (
        <li
          key={step}
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
            {progressLabel && <span className="text-xs text-muted tabular-nums">{progressLabel}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}
