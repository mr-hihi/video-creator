"use client";

import type { ChangeEvent } from "react";
import { buildButtonClassName, type ButtonVariant } from "./buttonStyles";

interface FileUploadButtonProps {
  label: string;
  acceptedExtensions: readonly string[];
  variant?: ButtonVariant;
  isDisabled?: boolean;
  onFileSelect: (file: File) => void;
}

export function FileUploadButton({
  label,
  acceptedExtensions,
  variant = "secondary",
  isDisabled = false,
  onFileSelect,
}: FileUploadButtonProps) {
  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) onFileSelect(file);
  }

  return (
    <label
      className={`${buildButtonClassName(variant)} cursor-pointer has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-50 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent`}
    >
      {label}
      <input
        type="file"
        accept={acceptedExtensions.join(",")}
        disabled={isDisabled}
        onChange={handleChange}
        className="sr-only"
      />
    </label>
  );
}
