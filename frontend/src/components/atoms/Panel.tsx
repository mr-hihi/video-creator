import type { ReactNode } from "react";

interface PanelProps {
  title: ReactNode;
  headerAction?: ReactNode;
  children: ReactNode;
}

export function Panel({ title, headerAction, children }: PanelProps) {
  return (
    <section className="rounded-xl border border-border bg-surface p-4 shadow-sm sm:p-6">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="min-w-0 text-lg font-semibold break-words">{title}</h2>
        {headerAction}
      </header>
      {children}
    </section>
  );
}
