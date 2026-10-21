"use client";

import { useEffect, useId, useState } from "react";

const LABEL_CLASS_NAME = "text-sm font-medium";
const ESCAPE_KEY = "Escape";

interface FieldLabelProps {
  htmlFor: string;
  label: string;
  helpText?: string;
}

interface FieldHelpProps {
  label: string;
  helpText: string;
}

export function FieldLabel({ htmlFor, label, helpText }: FieldLabelProps) {
  const labelElement = (
    <label htmlFor={htmlFor} className={LABEL_CLASS_NAME}>
      {label}
    </label>
  );
  if (!helpText) return labelElement;

  return (
    <div className="relative flex items-center gap-1.5">
      {labelElement}
      <FieldHelp label={label} helpText={helpText} />
    </div>
  );
}

function FieldHelp({ label, helpText }: FieldHelpProps) {
  const tooltipId = useId();
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    function hideOnEscape(event: KeyboardEvent) {
      if (event.key === ESCAPE_KEY) setIsOpen(false);
    }
    document.addEventListener("keydown", hideOnEscape);
    return () => document.removeEventListener("keydown", hideOnEscape);
  }, [isOpen]);

  return (
    <>
      <button
        type="button"
        aria-label={`About ${label}`}
        aria-describedby={tooltipId}
        onMouseEnter={() => setIsOpen(true)}
        onMouseLeave={() => setIsOpen(false)}
        onFocus={() => setIsOpen(true)}
        onBlur={() => setIsOpen(false)}
        className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-border text-xs font-semibold text-muted transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-accent"
      >
        i
      </button>
      <span
        id={tooltipId}
        role="tooltip"
        hidden={!isOpen}
        className="absolute inset-x-0 top-full z-10 mt-1 max-w-sm rounded-lg border border-border bg-surface px-3 py-2 text-xs text-foreground shadow-md"
      >
        {helpText}
      </span>
    </>
  );
}
