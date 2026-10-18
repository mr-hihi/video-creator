import { Badge, type BadgeTone } from "@/components/atoms/Badge";
import type { FilmCloneStatus } from "@/features/filmClones/types";

const CLONE_STATUS_BADGES: Record<FilmCloneStatus, { label: string; tone: BadgeTone }> = {
  running: { label: "Running", tone: "info" },
  waiting: { label: "Waiting", tone: "neutral" },
  done: { label: "Done", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
};

interface CloneStatusBadgeProps {
  status: FilmCloneStatus;
}

export function CloneStatusBadge({ status }: CloneStatusBadgeProps) {
  const { label, tone } = CLONE_STATUS_BADGES[status];
  return <Badge tone={tone}>{label}</Badge>;
}
