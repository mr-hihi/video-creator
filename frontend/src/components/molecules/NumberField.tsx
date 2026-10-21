"use client";

import { useId } from "react";
import { FieldLabel } from "@/components/atoms/FieldLabel";
import { NumberInput } from "@/components/atoms/NumberInput";

interface NumberFieldProps {
  label: string;
  value: string;
  min: number;
  max?: number;
  hint?: string;
  helpText?: string;
  isDisabled?: boolean;
  onChange: (value: string) => void;
}

export function NumberField({
  label,
  value,
  min,
  max,
  hint,
  helpText,
  isDisabled = false,
  onChange,
}: NumberFieldProps) {
  const inputId = useId();
  const hintId = useId();

  return (
    <div className="flex flex-col gap-2">
      <FieldLabel htmlFor={inputId} label={label} helpText={helpText} />
      <NumberInput
        id={inputId}
        value={value}
        min={min}
        max={max}
        step={1}
        aria-describedby={hint ? hintId : undefined}
        disabled={isDisabled}
        onChange={(event) => onChange(event.target.value)}
      />
      {hint && (
        <span id={hintId} className="text-xs text-muted">
          {hint}
        </span>
      )}
    </div>
  );
}
