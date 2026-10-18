"use client";

import { useId, type ChangeEvent } from "react";

interface FilePickerFieldProps {
  label: string;
  acceptedExtensions: readonly string[];
  hint?: string;
  isDisabled?: boolean;
  onFileSelect: (file: File | undefined) => void;
}

export function FilePickerField({ label, acceptedExtensions, hint, isDisabled = false, onFileSelect }: FilePickerFieldProps) {
  const inputId = useId();
  const acceptedId = useId();
  const hintId = useId();

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    onFileSelect(event.target.files?.[0]);
  }

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={inputId} className="text-sm font-medium">
        {label}
      </label>
      <input
        id={inputId}
        type="file"
        accept={acceptedExtensions.join(",")}
        disabled={isDisabled}
        aria-describedby={hint ? `${acceptedId} ${hintId}` : acceptedId}
        onChange={handleChange}
        className="block w-full min-w-0 text-sm text-foreground file:mr-3 file:rounded-lg file:border file:border-border file:bg-surface file:px-3 file:py-1.5 file:text-sm file:text-foreground focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-50"
      />
      <span id={acceptedId} className="text-xs text-muted">
        Accepted: {acceptedExtensions.join(" ")}
      </span>
      {hint && (
        <span id={hintId} className="text-xs text-muted">
          {hint}
        </span>
      )}
    </div>
  );
}
