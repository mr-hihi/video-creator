import type { SelectOption } from "./Select";

const SELECTED_SEGMENT_CLASS_NAME = "bg-surface text-foreground shadow-sm";
const UNSELECTED_SEGMENT_CLASS_NAME = "text-muted hover:text-foreground";

interface SegmentedControlProps<TValue extends string> {
  label: string;
  value: TValue;
  options: readonly SelectOption<TValue>[];
  isDisabled?: boolean;
  onChange: (value: TValue) => void;
}

export function SegmentedControl<TValue extends string>({
  label,
  value,
  options,
  isDisabled = false,
  onChange,
}: SegmentedControlProps<TValue>) {
  return (
    <div role="radiogroup" aria-label={label} className="flex w-full rounded-lg border border-border bg-background p-1 sm:w-fit">
      {options.map((option) => {
        const isSelected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={isSelected}
            disabled={isDisabled}
            onClick={() => onChange(option.value)}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50 sm:flex-none ${
              isSelected ? SELECTED_SEGMENT_CLASS_NAME : UNSELECTED_SEGMENT_CLASS_NAME
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
