import Link from "next/link";
import type { ReactNode } from "react";
import { PageTemplate } from "./PageTemplate";

interface JobDetailTemplateProps {
  backHref: string;
  backLabel: string;
  children: ReactNode;
}

export function JobDetailTemplate({ backHref, backLabel, children }: JobDetailTemplateProps) {
  return (
    <PageTemplate>
      <Link href={backHref} className="self-start text-sm text-accent hover:underline">
        ← {backLabel}
      </Link>
      {children}
    </PageTemplate>
  );
}
