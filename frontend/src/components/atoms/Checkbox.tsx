import type { InputHTMLAttributes } from "react";

type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, "className" | "type">;

export function Checkbox(inputProps: CheckboxProps) {
  return (
    <input
      type="checkbox"
      className="size-4 rounded border-border accent-accent focus-visible:outline-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50"
      {...inputProps}
    />
  );
}
