import type { SelectOption } from "@/components/atoms/Select";
import { CheckboxField } from "./CheckboxField";

interface CheckboxListProps {
  options: readonly SelectOption<string>[];
  selectedValues: readonly string[];
  emptyText: string;
  isDisabled?: boolean;
  onChange: (selectedValues: string[]) => void;
}

export function CheckboxList({ options, selectedValues, emptyText, isDisabled = false, onChange }: CheckboxListProps) {
  const selectedValueSet = new Set(selectedValues);

  function toggleValue(value: string, isChecked: boolean) {
    onChange(isChecked ? [...selectedValues, value] : selectedValues.filter((selectedValue) => selectedValue !== value));
  }

  if (!options.length) return <p className="text-sm text-muted">{emptyText}</p>;
  return (
    <ul className="flex max-h-48 flex-col gap-1.5 overflow-y-auto">
      {options.map((option) => (
        <li key={option.value}>
          <CheckboxField
            label={option.label}
            isChecked={selectedValueSet.has(option.value)}
            isDisabled={isDisabled}
            onChange={(isChecked) => toggleValue(option.value, isChecked)}
          />
        </li>
      ))}
    </ul>
  );
}
