import { ProgressBar } from "@/components/atoms/ProgressBar";

const UPLOAD_COMPLETE_PERCENT = 100;

interface UploadProgressProps {
  uploadedPercent: number;
}

export function UploadProgress({ uploadedPercent }: UploadProgressProps) {
  const statusText =
    uploadedPercent >= UPLOAD_COMPLETE_PERCENT ? "Upload complete, creating the job…" : `Uploading… ${uploadedPercent}%`;

  return (
    <div className="flex flex-col gap-2">
      <ProgressBar percent={uploadedPercent} label="Upload progress" />
      <span className="text-xs text-muted" aria-live="polite">
        {statusText}
      </span>
    </div>
  );
}
