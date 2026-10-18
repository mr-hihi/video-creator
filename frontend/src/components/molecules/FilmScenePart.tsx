import type { ReactNode } from "react";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";

interface FilmScenePartProps {
  title: string;
  media: ReactNode;
  statusText: string | undefined;
  errorMessage: string | null;
  actionErrorMessage: string | undefined;
  children: ReactNode;
}

export function FilmScenePart({
  title,
  media,
  statusText,
  errorMessage,
  actionErrorMessage,
  children,
}: FilmScenePartProps) {
  return (
    <section className="flex min-w-0 flex-col gap-2">
      <h4 className="text-xs font-medium text-muted">{title}</h4>
      {media}
      {statusText && (
        <p aria-live="polite" className="text-xs text-muted">
          {statusText}
        </p>
      )}
      {errorMessage && <ErrorAlert>{errorMessage}</ErrorAlert>}
      {actionErrorMessage && <ErrorAlert>{actionErrorMessage}</ErrorAlert>}
      <div className="flex flex-wrap gap-2">{children}</div>
    </section>
  );
}
