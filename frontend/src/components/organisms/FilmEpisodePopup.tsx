"use client";

import { useCallback, useEffect, useRef, type SyntheticEvent } from "react";
import { useRouter } from "next/navigation";
import { UNSAVED_CHANGES_CONFIRMATION, UnsavedChangesContext } from "@/lib/unsavedChanges";
import { FilmEpisodePanel } from "./FilmEpisodePanel";

interface FilmEpisodePopupProps {
  projectId: string;
  episodeNumberText: string;
}

export function FilmEpisodePopup({ projectId, episodeNumberText }: FilmEpisodePopupProps) {
  const router = useRouter();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const unsavedFormKeysRef = useRef(new Set<string>());

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  const reportUnsavedChanges = useCallback((formKey: string, hasUnsavedChanges: boolean) => {
    if (hasUnsavedChanges) unsavedFormKeysRef.current.add(formKey);
    else unsavedFormKeysRef.current.delete(formKey);
  }, []);

  function closePopup() {
    if (unsavedFormKeysRef.current.size > 0 && !window.confirm(UNSAVED_CHANGES_CONFIRMATION)) return;
    router.back();
  }

  function handleCancel(event: SyntheticEvent<HTMLDialogElement>) {
    // React bubbles the cancel event of a nested dialog (enlarged image, edit prompt) up to this one.
    if (event.target !== event.currentTarget) return;
    event.preventDefault();
    closePopup();
  }

  return (
    <dialog
      ref={dialogRef}
      aria-label={`Episode ${episodeNumberText}`}
      onCancel={handleCancel}
      className="m-auto h-[92dvh] w-[min(96vw,80rem)] overflow-y-auto overscroll-contain rounded-xl border border-border bg-background p-4 text-foreground backdrop:bg-background/80 sm:p-6"
    >
      <UnsavedChangesContext value={reportUnsavedChanges}>
        <FilmEpisodePanel projectId={projectId} episodeNumberText={episodeNumberText} onClose={closePopup} />
      </UnsavedChangesContext>
    </dialog>
  );
}
