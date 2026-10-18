import type { InputHTMLAttributes } from "react";

type NumberInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "className" | "type">;

export function NumberInput(inputProps: NumberInputProps) {
  return (
    <input
      type="number"
      inputMode="numeric"
      className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50 sm:w-32"
      {...inputProps}
    />
  );
}
