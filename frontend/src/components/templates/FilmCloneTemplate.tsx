import type { ReactNode } from "react";
import { Panel } from "@/components/atoms/Panel";
import { FILM_CLONE_DESCRIPTION } from "@/features/filmClones/constants";
import { PageTemplate } from "./PageTemplate";

interface FilmCloneTemplateProps {
  cloneForm: ReactNode;
  cloneHistory: ReactNode;
}

export function FilmCloneTemplate({ cloneForm, cloneHistory }: FilmCloneTemplateProps) {
  return (
    <PageTemplate>
      <p className="max-w-prose text-sm text-muted">{FILM_CLONE_DESCRIPTION}</p>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Panel title="New clone">{cloneForm}</Panel>
        <Panel title="Clone history">{cloneHistory}</Panel>
      </div>
    </PageTemplate>
  );
}
