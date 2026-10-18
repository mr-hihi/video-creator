import type { TextareaHTMLAttributes } from "react";

type TextAreaProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "className">;

export function TextArea(textAreaProps: TextAreaProps) {
  return (
    <textarea
      className="min-h-40 w-full resize-y rounded-lg border border-border bg-surface px-3 py-2 font-mono text-xs leading-relaxed text-foreground placeholder:text-muted focus-visible:outline-2 focus-visible:outline-accent read-only:bg-background disabled:opacity-50"
      {...textAreaProps}
    />
  );
}
