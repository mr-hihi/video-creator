import type { ReactNode } from "react";

export interface SummaryItem {
  term: string;
  description: ReactNode;
}

interface SummaryListProps {
  items: readonly SummaryItem[];
}

export function SummaryList({ items }: SummaryListProps) {
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
      {items.map(({ term, description }) => (
        <div key={term} className="flex min-w-0 flex-col gap-0.5">
          <dt className="text-xs text-muted">{term}</dt>
          <dd className="text-sm break-all">{description}</dd>
        </div>
      ))}
    </dl>
  );
}
