import Link from "next/link";
import type { SelectOption } from "@/components/atoms/Select";
import { ADD_VOICE_LABEL } from "@/features/films/constants";
import type { ProjectSettingsDraft } from "@/features/films/types";
import { buildFilmLibraryPath } from "@/features/films/utils";
import { CheckboxField } from "./CheckboxField";
import { SelectField } from "./SelectField";

type NarrationSettings = Pick<ProjectSettingsDraft, "allowNarration" | "narratorVoiceId">;

interface FilmNarrationFieldsProps {
  settings: NarrationSettings;
  voiceOptions: readonly SelectOption<string>[];
  isDisabled: boolean;
  onChange: (changes: Partial<NarrationSettings>) => void;
}

export function FilmNarrationFields({ settings, voiceOptions, isDisabled, onChange }: FilmNarrationFieldsProps) {
  return (
    <div className="flex flex-col gap-3">
      <CheckboxField
        label="Narration"
        isChecked={settings.allowNarration}
        isDisabled={isDisabled}
        onChange={(allowNarration) => onChange({ allowNarration })}
      />
      <div className="flex flex-col gap-1">
        <SelectField<string>
          label="Narrator voice"
          value={settings.narratorVoiceId}
          options={voiceOptions}
          isDisabled={isDisabled || !settings.allowNarration}
          onChange={(narratorVoiceId) => onChange({ narratorVoiceId })}
        />
        <Link href={buildFilmLibraryPath("voices")} className="self-start text-xs text-accent hover:underline">
          {ADD_VOICE_LABEL}
        </Link>
      </div>
    </div>
  );
}
