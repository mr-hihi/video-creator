import type { ReactNode } from "react";
import { Panel } from "@/components/atoms/Panel";
import { FILM_ANALYSIS_DESCRIPTION } from "@/lib/constants";
import { PageTemplate } from "./PageTemplate";

interface FilmAnalysisTemplateProps {
  analysisForm: ReactNode;
  analysisHistory: ReactNode;
}

export function FilmAnalysisTemplate({ analysisForm, analysisHistory }: FilmAnalysisTemplateProps) {
  return (
    <PageTemplate>
      <p className="max-w-prose text-sm text-muted">{FILM_ANALYSIS_DESCRIPTION}</p>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Panel title="New analysis">{analysisForm}</Panel>
        <Panel title="Analysis history">{analysisHistory}</Panel>
      </div>
    </PageTemplate>
  );
}
