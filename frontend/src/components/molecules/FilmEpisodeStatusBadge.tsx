import { Badge, type BadgeTone } from "@/components/atoms/Badge";
import { EPISODE_STATUS_LABELS } from "@/features/films/constants";
import type { EpisodeStatus } from "@/features/films/types";

const EPISODE_STATUS_TONES: Record<EpisodeStatus, BadgeTone> = {
  draft: "neutral",
  running: "info",
  paused: "neutral",
  done: "success",
  failed: "danger",
};

interface FilmEpisodeStatusBadgeProps {
  status: EpisodeStatus;
}

export function FilmEpisodeStatusBadge({ status }: FilmEpisodeStatusBadgeProps) {
  return <Badge tone={EPISODE_STATUS_TONES[status]}>{EPISODE_STATUS_LABELS[status]}</Badge>;
}
