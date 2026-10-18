"use client";

import { useId, type ReactNode } from "react";
import { TextArea } from "@/components/atoms/TextArea";

interface TextAreaFieldProps {
  label: ReactNode;
  value: string;
  maxLength?: number;
  hint?: string;
  isDisabled?: boolean;
  onChange: (value: string) => void;
}

export function TextAreaField({ label, value, maxLength, hint, isDisabled = false, onChange }: TextAreaFieldProps) {
  const textAreaId = useId();
  const counterId = useId();
  const hintId = useId();
  const describedByIds = [maxLength === undefined ? "" : counterId, hint ? hintId : ""].filter(Boolean).join(" ");

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={textAreaId} className="text-sm font-medium">
        {label}
      </label>
      <TextArea
        id={textAreaId}
        value={value}
        rows={10}
        spellCheck={false}
        aria-describedby={describedByIds || undefined}
        disabled={isDisabled}
        onChange={(event) => onChange(event.target.value)}
      />
      {describedByIds && (
        <div className="flex flex-wrap items-start justify-between gap-2">
          {hint && (
            <span id={hintId} className="text-xs text-muted">
              {hint}
            </span>
          )}
          {maxLength !== undefined && (
            <span id={counterId} className="ml-auto text-xs text-muted tabular-nums">
              {value.length} / {maxLength}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
