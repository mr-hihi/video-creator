import type { ReactNode } from "react";

interface PlaceholderMessageProps {
  children: ReactNode;
}

export function PlaceholderMessage({ children }: PlaceholderMessageProps) {
  return <p className="py-6 text-center text-sm text-muted">{children}</p>;
}
