import type { SelectOption } from "@/components/atoms/Select";
import { CheckboxList } from "./CheckboxList";

interface CheckboxListFieldProps {
  label: string;
  options: readonly SelectOption<string>[];
  selectedValues: readonly string[];
  emptyText: string;
  isDisabled?: boolean;
  onChange: (selectedValues: string[]) => void;
}

export function CheckboxListField({ label, ...checkboxListProps }: CheckboxListFieldProps) {
  return (
    <fieldset className="flex min-w-0 flex-col gap-2">
      <legend className="mb-2 text-sm font-medium">{label}</legend>
      <CheckboxList {...checkboxListProps} />
    </fieldset>
  );
}
