import type { ReactNode } from "react";

export type BadgeTone = "neutral" | "info" | "success" | "danger";

const BADGE_TONE_CLASS_NAMES: Record<BadgeTone, string> = {
  neutral: "bg-foreground/10 text-foreground/80",
  info: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
  success: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  danger: "bg-red-500/15 text-red-700 dark:text-red-300",
};

interface BadgeProps {
  tone: BadgeTone;
  children: ReactNode;
}

export function Badge({ tone, children }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${BADGE_TONE_CLASS_NAMES[tone]}`}
    >
      {children}
    </span>
  );
}
