const MIN_PERCENT = 0;
const MAX_PERCENT = 100;

interface ProgressBarProps {
  percent: number;
  label: string;
}

export function ProgressBar({ percent, label }: ProgressBarProps) {
  const clampedPercent = Math.min(Math.max(percent, MIN_PERCENT), MAX_PERCENT);

  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={MIN_PERCENT}
      aria-valuemax={MAX_PERCENT}
      aria-valuenow={clampedPercent}
      className="h-2 w-full overflow-hidden rounded-full bg-foreground/10"
    >
      <div className="h-full rounded-full bg-accent transition-[width]" style={{ width: `${clampedPercent}%` }} />
    </div>
  );
}
