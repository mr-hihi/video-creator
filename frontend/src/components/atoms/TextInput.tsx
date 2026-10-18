import type { InputHTMLAttributes } from "react";

export type TextInputType = "text" | "password";

interface TextInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "className" | "type"> {
  type?: TextInputType;
}

export function TextInput({ type = "text", ...inputProps }: TextInputProps) {
  return (
    <input
      type={type}
      className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50"
      {...inputProps}
    />
  );
}
