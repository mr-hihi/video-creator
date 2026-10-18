import type { SelectOption } from "@/components/atoms/Select";
import { labelsToSelectOptions } from "@/features/filmClones/utils";
import { FILM_LANGUAGE_LABELS, LOOK_FIXED_HINT, ORIENTATION_LABELS } from "@/features/films/constants";
import type { FilmLanguage, FilmLookSettings, Orientation } from "@/features/films/types";
import { SelectField } from "./SelectField";

const FILM_LANGUAGE_OPTIONS = labelsToSelectOptions(FILM_LANGUAGE_LABELS);
const ORIENTATION_OPTIONS = labelsToSelectOptions(ORIENTATION_LABELS);

interface FilmLookFieldsProps {
  settings: FilmLookSettings;
  styleOptions: readonly SelectOption<string>[];
  isLookFixed: boolean;
  isDisabled: boolean;
  onChange: (changes: Partial<FilmLookSettings>) => void;
}

export function FilmLookFields({ settings, styleOptions, isLookFixed, isDisabled, onChange }: FilmLookFieldsProps) {
  const lookHint = isLookFixed ? LOOK_FIXED_HINT : undefined;

  return (
    <>
      <SelectField<FilmLanguage>
        label="Language"
        value={settings.language}
        options={FILM_LANGUAGE_OPTIONS}
        isDisabled={isDisabled}
        onChange={(language) => onChange({ language })}
      />
      <SelectField<Orientation>
        label="Frame"
        value={settings.orientation}
        options={ORIENTATION_OPTIONS}
        hint={lookHint}
        isDisabled={isDisabled || isLookFixed}
        onChange={(orientation) => onChange({ orientation })}
      />
      <SelectField<string>
        label="Style"
        value={settings.styleId}
        options={styleOptions}
        hint={lookHint}
        isDisabled={isDisabled || isLookFixed}
        onChange={(styleId) => onChange({ styleId })}
      />
    </>
  );
}
