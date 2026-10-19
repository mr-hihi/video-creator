"use client";

import { useEffect, useRef, type ReactNode, type SyntheticEvent } from "react";

interface ModalDialogProps {
  title: string;
  isClosable: boolean;
  onClose: () => void;
  children: ReactNode;
}

export function ModalDialog({ title, isClosable, onClose, children }: ModalDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  function handleCancel(event: SyntheticEvent<HTMLDialogElement>) {
    if (!isClosable) event.preventDefault();
  }

  return (
    <dialog
      ref={dialogRef}
      aria-label={title}
      onCancel={handleCancel}
      onClose={onClose}
      className="m-auto max-h-[90dvh] w-[min(92vw,40rem)] overflow-y-auto rounded-xl border border-border bg-surface p-0 text-foreground backdrop:bg-background/80"
    >
      <div className="flex flex-col gap-4 p-4 sm:p-6">
        <h2 className="text-lg font-semibold">{title}</h2>
        {children}
      </div>
    </dialog>
  );
}
