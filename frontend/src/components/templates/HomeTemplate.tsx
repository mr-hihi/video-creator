import type { ReactNode } from "react";
import { Panel } from "@/components/atoms/Panel";
import { APP_DESCRIPTION } from "@/lib/constants";
import { PageTemplate } from "./PageTemplate";

interface HomeTemplateProps {
  conversionForm: ReactNode;
  jobList: ReactNode;
}

export function HomeTemplate({ conversionForm, jobList }: HomeTemplateProps) {
  return (
    <PageTemplate>
      <p className="max-w-prose text-sm text-muted">{APP_DESCRIPTION}</p>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Panel title="New conversion">{conversionForm}</Panel>
        <Panel title="Recent jobs">{jobList}</Panel>
      </div>
    </PageTemplate>
  );
}
