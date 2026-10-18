import { Fragment, type ChangeEvent } from "react";

export interface SelectOption<TValue extends string> {
  value: TValue;
  label: string;
  group?: string;
}

interface SelectOptionGroup<TValue extends string> {
  label: string | undefined;
  options: SelectOption<TValue>[];
}

interface SelectProps<TValue extends string> {
  id: string;
  value: TValue;
  options: readonly SelectOption<TValue>[];
  describedById?: string;
  isDisabled?: boolean;
  onChange: (value: TValue) => void;
}

export function Select<TValue extends string>({
  id,
  value,
  options,
  describedById,
  isDisabled = false,
  onChange,
}: SelectProps<TValue>) {
  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    const selectedOption = options.find((option) => option.value === event.target.value);
    if (selectedOption) onChange(selectedOption.value);
  }

  return (
    <select
      id={id}
      value={value}
      aria-describedby={describedById}
      disabled={isDisabled}
      onChange={handleChange}
      className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50"
    >
      {groupConsecutiveOptions(options).map((optionGroup) => {
        const groupKey = optionGroup.options[0].value;
        const optionElements = optionGroup.options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ));
        if (optionGroup.label === undefined) return <Fragment key={groupKey}>{optionElements}</Fragment>;
        return (
          <optgroup key={groupKey} label={optionGroup.label}>
            {optionElements}
          </optgroup>
        );
      })}
    </select>
  );
}

function groupConsecutiveOptions<TValue extends string>(
  options: readonly SelectOption<TValue>[],
): SelectOptionGroup<TValue>[] {
  return options.reduce<SelectOptionGroup<TValue>[]>((optionGroups, option) => {
    const lastGroup = optionGroups.at(-1);
    if (lastGroup && lastGroup.label === option.group) {
      return [...optionGroups.slice(0, -1), { ...lastGroup, options: [...lastGroup.options, option] }];
    }
    return [...optionGroups, { label: option.group, options: [option] }];
  }, []);
}
