"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/atoms/Button";

const COPIED_LABEL_DURATION_MS = 2_000;
const DEFAULT_COPY_LABEL = "Copy";

interface CopyButtonProps {
  text: string;
  label?: string;
}

export function CopyButton({ text, label = DEFAULT_COPY_LABEL }: CopyButtonProps) {
  const [isCopied, setIsCopied] = useState(false);

  useEffect(() => {
    if (!isCopied) return;
    const timeoutId = window.setTimeout(() => setIsCopied(false), COPIED_LABEL_DURATION_MS);
    return () => window.clearTimeout(timeoutId);
  }, [isCopied]);

  async function handleCopy() {
    await navigator.clipboard.writeText(text);
    setIsCopied(true);
  }

  return (
    <Button variant="secondary" onClick={handleCopy}>
      {isCopied ? "Copied" : label}
    </Button>
  );
}
