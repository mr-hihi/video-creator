"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { EDIT_PROMPT_MAX_LENGTH } from "@/features/films/constants";
import { TextAreaField } from "./TextAreaField";

interface EditPromptDialogProps {
  title: string;
  isOpen: boolean;
  isSubmitting: boolean;
  errorMessage: string | undefined;
  onApply: (prompt: string) => void;
  onClose: () => void;
}

export function EditPromptDialog({ title, isOpen, isSubmitting, errorMessage, onApply, onClose }: EditPromptDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [prompt, setPrompt] = useState("");

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (isOpen && !dialog.open) dialog.showModal();
    if (!isOpen && dialog.open) dialog.close();
  }, [isOpen]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onApply(prompt);
  }

  return (
    <dialog
      ref={dialogRef}
      aria-label={title}
      onClose={onClose}
      className="m-auto w-[min(92vw,40rem)] rounded-xl border border-border bg-surface p-0 text-foreground backdrop:bg-background/80"
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-4 sm:p-6">
        <h2 className="text-lg font-semibold">{title}</h2>
        <TextAreaField
          label="Edit prompt"
          value={prompt}
          maxLength={EDIT_PROMPT_MAX_LENGTH}
          isDisabled={isSubmitting}
          onChange={setPrompt}
        />
        {errorMessage && <ErrorAlert>{errorMessage}</ErrorAlert>}
        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={!prompt.trim() || isSubmitting}>
            Apply
          </Button>
          <Button variant="secondary" disabled={isSubmitting} onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </dialog>
  );
}
