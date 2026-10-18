import type { AiActivity } from "@/features/filmClones/types";
import { describeAiActivity } from "@/features/filmClones/utils";

interface AiActivityLineProps {
  activity: AiActivity;
  nowMs: number;
}

export function AiActivityLine({ activity, nowMs }: AiActivityLineProps) {
  return (
    <p aria-live="polite" className="text-sm text-muted">
      {describeAiActivity(activity, nowMs)}
    </p>
  );
}
