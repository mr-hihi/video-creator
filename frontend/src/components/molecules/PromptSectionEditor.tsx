import { Badge } from "@/components/atoms/Badge";
import { Button } from "@/components/atoms/Button";
import { TextArea } from "@/components/atoms/TextArea";
import {
  CUSTOMIZED_PROMPT_BADGE_LABEL,
  DEFAULT_PROMPT_BADGE_LABEL,
  MAX_PROMPT_LENGTH,
  type PromptSection,
} from "@/features/promptPresets/constants";
import { TextAreaField } from "./TextAreaField";

interface PromptSectionEditorProps {
  section: PromptSection;
  value: string;
  defaultValue: string;
  appAddedPart: string;
  onChange: (value: string) => void;
}

export function PromptSectionEditor({ section, value, defaultValue, appAddedPart, onChange }: PromptSectionEditorProps) {
  const isDefault = value === defaultValue;

  return (
    <section className="flex flex-col gap-3 border-t border-border pt-5 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-col gap-0.5">
          <h3 className="text-base font-semibold">{section.title}</h3>
          <span className="text-xs text-muted">Used by {section.usedBy}</span>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={isDefault ? "neutral" : "info"}>
            {isDefault ? DEFAULT_PROMPT_BADGE_LABEL : CUSTOMIZED_PROMPT_BADGE_LABEL}
          </Badge>
          <Button variant="secondary" disabled={isDefault} onClick={() => onChange(defaultValue)}>
            Reset to default
          </Button>
        </div>
      </div>
      <TextAreaField label="Instructions" value={value} maxLength={MAX_PROMPT_LENGTH} onChange={onChange} />
      <details className="rounded-lg border border-border bg-background px-3 py-2">
        <summary className="cursor-pointer text-sm text-muted">Added by the app</summary>
        <div className="mt-2">
          <TextArea value={appAddedPart} rows={6} readOnly aria-label={`${section.title} — added by the app`} />
        </div>
      </details>
    </section>
  );
}
