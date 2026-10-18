"use client";

import { useId, type HTMLAttributes } from "react";
import { TextInput, type TextInputType } from "@/components/atoms/TextInput";

const AUTOCOMPLETE_BY_INPUT_TYPE: Record<TextInputType, string> = {
  text: "off",
  password: "new-password",
};

interface TextFieldProps {
  label: string;
  value: string;
  type?: TextInputType;
  placeholder?: string;
  hint?: string;
  inputMode?: HTMLAttributes<HTMLInputElement>["inputMode"];
  isDisabled?: boolean;
  onChange: (value: string) => void;
}

export function TextField({
  label,
  value,
  type = "text",
  placeholder,
  hint,
  inputMode,
  isDisabled = false,
  onChange,
}: TextFieldProps) {
  const inputId = useId();
  const hintId = useId();

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={inputId} className="text-sm font-medium">
        {label}
      </label>
      <TextInput
        id={inputId}
        type={type}
        value={value}
        placeholder={placeholder}
        inputMode={inputMode}
        autoComplete={AUTOCOMPLETE_BY_INPUT_TYPE[type]}
        spellCheck={false}
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
