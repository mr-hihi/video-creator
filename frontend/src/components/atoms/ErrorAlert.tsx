import type { ReactNode } from "react";

interface ErrorAlertProps {
  children: ReactNode;
}

export function ErrorAlert({ children }: ErrorAlertProps) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm break-words text-red-700 dark:text-red-300"
    >
      {children}
    </div>
  );
}
