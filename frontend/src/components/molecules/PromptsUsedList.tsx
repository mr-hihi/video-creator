import { TextArea } from "@/components/atoms/TextArea";
import { PROMPT_SECTIONS } from "@/features/promptPresets/constants";
import type { PresetPrompts } from "@/features/promptPresets/types";
import { CopyButton } from "./CopyButton";

interface PromptsUsedListProps {
  prompts: Partial<PresetPrompts>;
}

export function PromptsUsedList({ prompts }: PromptsUsedListProps) {
  return (
    <div className="flex flex-col gap-5">
      {PROMPT_SECTIONS.map(({ key, title }) => {
        const prompt = prompts[key];
        if (prompt === undefined) return null;
        return (
          <section key={key} className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-medium">{title}</h3>
              <CopyButton text={prompt} />
            </div>
            <TextArea value={prompt} rows={6} readOnly aria-label={title} />
          </section>
        );
      })}
    </div>
  );
}
