"use client";

import { useId, type ReactNode } from "react";
import { FieldLabel } from "@/components/atoms/FieldLabel";
import { Select, type SelectOption } from "@/components/atoms/Select";

interface SelectFieldProps<TValue extends string> {
  label: string;
  value: TValue;
  options: readonly SelectOption<TValue>[];
  hint?: string;
  helpText?: string;
  isDisabled?: boolean;
  action?: ReactNode;
  onChange: (value: TValue) => void;
}

export function SelectField<TValue extends string>({
  label,
  hint,
  helpText,
  action,
  ...selectProps
}: SelectFieldProps<TValue>) {
  const selectId = useId();
  const hintId = useId();
  const select = <Select id={selectId} describedById={hint ? hintId : undefined} {...selectProps} />;

  return (
    <div className="flex flex-col gap-2">
      <FieldLabel htmlFor={selectId} label={label} helpText={helpText} />
      {action ? (
        <div className="flex flex-wrap items-center gap-2">
          <div className="min-w-0 flex-1 basis-48">{select}</div>
          {action}
        </div>
      ) : (
        select
      )}
      {hint && (
        <span id={hintId} className="text-xs text-muted">
          {hint}
        </span>
      )}
    </div>
  );
}
