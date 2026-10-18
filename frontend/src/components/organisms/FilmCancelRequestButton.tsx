"use client";

import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import type { GenerationRequest } from "@/features/filmClones/types";
import { useCancelFilmRequestMutation } from "@/features/films/queries";

interface FilmCancelRequestButtonProps {
  request: GenerationRequest | undefined;
  isDisabled: boolean;
}

export function FilmCancelRequestButton({ request, isDisabled }: FilmCancelRequestButtonProps) {
  const cancelMutation = useCancelFilmRequestMutation();

  if (request?.status !== "queued") return null;

  return (
    <>
      <Button
        variant="secondary"
        disabled={isDisabled || cancelMutation.isPending}
        onClick={() => cancelMutation.mutate(request.id)}
      >
        Cancel
      </Button>
      {cancelMutation.isError && (
        <div className="w-full">
          <ErrorAlert>{cancelMutation.error.message}</ErrorAlert>
        </div>
      )}
    </>
  );
}
