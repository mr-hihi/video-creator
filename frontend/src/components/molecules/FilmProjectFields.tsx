import type { SelectOption } from "@/components/atoms/Select";
import {
  CLIP_DURATION_OPTIONS,
  DEFAULT_CLIP_LENGTH_HINT,
  PREMISE_HINT,
  PROJECT_DESCRIPTION_MAX_LENGTH,
} from "@/features/films/constants";
import type { ProjectSettingsDraft } from "@/features/films/types";
import { CheckboxField } from "./CheckboxField";
import { FilmLookFields } from "./FilmLookFields";
import { FilmNarrationFields } from "./FilmNarrationFields";
import { SelectField } from "./SelectField";
import { TextAreaField } from "./TextAreaField";
import { TextField } from "./TextField";

interface FilmProjectFieldsProps {
  draft: ProjectSettingsDraft;
  styleOptions: readonly SelectOption<string>[];
  voiceOptions: readonly SelectOption<string>[];
  isLookFixed: boolean;
  isDisabled: boolean;
  onChange: (changes: Partial<ProjectSettingsDraft>) => void;
}

export function FilmProjectFields({
  draft,
  styleOptions,
  voiceOptions,
  isLookFixed,
  isDisabled,
  onChange,
}: FilmProjectFieldsProps) {
  return (
    <>
      <TextField label="Name" value={draft.name} isDisabled={isDisabled} onChange={(name) => onChange({ name })} />
      <TextAreaField
        label="Premise"
        value={draft.description}
        maxLength={PROJECT_DESCRIPTION_MAX_LENGTH}
        hint={PREMISE_HINT}
        isDisabled={isDisabled}
        onChange={(description) => onChange({ description })}
      />
      <FilmLookFields
        settings={draft}
        styleOptions={styleOptions}
        isLookFixed={isLookFixed}
        isDisabled={isDisabled}
        onChange={onChange}
      />
      <SelectField<string>
        label="Default clip length"
        value={draft.clipDurationS}
        options={CLIP_DURATION_OPTIONS}
        hint={DEFAULT_CLIP_LENGTH_HINT}
        isDisabled={isDisabled}
        onChange={(clipDurationS) => onChange({ clipDurationS })}
      />
      <CheckboxField
        label="Characters speak in clips"
        isChecked={draft.allowDialogue}
        isDisabled={isDisabled}
        onChange={(allowDialogue) => onChange({ allowDialogue })}
      />
      <FilmNarrationFields
        settings={draft}
        voiceOptions={voiceOptions}
        isDisabled={isDisabled}
        onChange={onChange}
      />
      <CheckboxField
        label="Background music"
        isChecked={draft.allowMusic}
        isDisabled={isDisabled}
        onChange={(allowMusic) => onChange({ allowMusic })}
      />
    </>
  );
}
