"use client";

import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { useOpenFlowTabMutation, useResumeGoogleFlowMutation } from "@/features/providers/queries";

interface GoogleFlowActionsProps {
  isPaused: boolean;
  isExtensionConnected: boolean;
}

export function GoogleFlowActions({ isPaused, isExtensionConnected }: GoogleFlowActionsProps) {
  const resumeMutation = useResumeGoogleFlowMutation();
  const openTabMutation = useOpenFlowTabMutation();
  const isBusy = resumeMutation.isPending || openTabMutation.isPending;
  const failedMutation = [resumeMutation, openTabMutation].find((mutation) => mutation.isError);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        {isPaused && (
          <Button variant="secondary" disabled={isBusy} onClick={() => resumeMutation.mutate()}>
            Resume now
          </Button>
        )}
        <Button variant="secondary" disabled={!isExtensionConnected || isBusy} onClick={() => openTabMutation.mutate()}>
          Open Flow tab
        </Button>
      </div>
      {failedMutation?.error && <ErrorAlert>{failedMutation.error.message}</ErrorAlert>}
    </div>
  );
}
