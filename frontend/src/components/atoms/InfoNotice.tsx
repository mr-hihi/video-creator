import type { ReactNode } from "react";

interface InfoNoticeProps {
  children: ReactNode;
}

export function InfoNotice({ children }: InfoNoticeProps) {
  return (
    <p
      role="status"
      className="rounded-lg border border-accent/30 bg-accent/10 px-4 py-3 text-sm break-words text-foreground"
    >
      {children}
    </p>
  );
}
