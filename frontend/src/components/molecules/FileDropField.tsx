"use client";

import { useId, useState, type ChangeEvent, type DragEvent } from "react";
import { formatFileSize } from "@/lib/format";
import { hasAcceptedExtension } from "@/lib/files";

interface FileDropFieldProps {
  label: string;
  acceptedExtensions: readonly string[];
  selectedFile: File | undefined;
  isDisabled: boolean;
  onFileSelect: (file: File) => void;
}

export function FileDropField({ label, acceptedExtensions, selectedFile, isDisabled, onFileSelect }: FileDropFieldProps) {
  const inputId = useId();
  const [isDragActive, setIsDragActive] = useState(false);
  const [rejectedFileName, setRejectedFileName] = useState("");

  function acceptFile(file: File) {
    if (!hasAcceptedExtension(file.name, acceptedExtensions)) {
      setRejectedFileName(file.name);
      return;
    }
    setRejectedFileName("");
    onFileSelect(file);
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) acceptFile(file);
  }

  function handleDragOver(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    if (!isDisabled) setIsDragActive(true);
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragActive(false);
    const file = event.dataTransfer.files[0];
    if (!isDisabled && file) acceptFile(file);
  }

  return (
    <div className="flex flex-col gap-2">
      <span className="text-sm font-medium">{label}</span>
      <label
        htmlFor={inputId}
        onDragOver={handleDragOver}
        onDragLeave={() => setIsDragActive(false)}
        onDrop={handleDrop}
        className={`flex cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-60 ${
          isDragActive ? "border-accent bg-accent/5" : "border-border hover:border-accent/60"
        }`}
      >
        <SelectedFileSummary selectedFile={selectedFile} />
        <span className="text-xs text-muted">Accepted: {acceptedExtensions.join(" ")}</span>
        <input
          id={inputId}
          type="file"
          accept={acceptedExtensions.join(",")}
          disabled={isDisabled}
          onChange={handleInputChange}
          className="sr-only"
        />
      </label>
      {rejectedFileName && (
        <p role="alert" className="text-sm text-red-700 dark:text-red-300">
          {rejectedFileName} is not a supported video file.
        </p>
      )}
    </div>
  );
}

function SelectedFileSummary({ selectedFile }: { selectedFile: File | undefined }) {
  if (!selectedFile) {
    return <span className="text-sm font-medium">Drop a video here or click to choose one</span>;
  }
  return (
    <span className="max-w-full text-sm font-medium break-all">
      {selectedFile.name} ({formatFileSize(selectedFile.size)})
    </span>
  );
}
