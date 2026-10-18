import type { ReactNode } from "react";
import { PageTemplate } from "./PageTemplate";

interface SettingsTemplateProps {
  children: ReactNode;
}

export function SettingsTemplate({ children }: SettingsTemplateProps) {
  return <PageTemplate>{children}</PageTemplate>;
}
