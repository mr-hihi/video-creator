import type { ReactNode } from "react";

interface SuccessNoticeProps {
  children: ReactNode;
}

export function SuccessNotice({ children }: SuccessNoticeProps) {
  return (
    <p
      role="status"
      className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm break-words text-emerald-700 dark:text-emerald-300"
    >
      {children}
    </p>
  );
}
