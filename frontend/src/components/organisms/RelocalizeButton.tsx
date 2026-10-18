"use client";

import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { RELOCALIZE_CONFIRMATION } from "@/features/filmClones/constants";
import { useRelocalizeFilmCloneMutation } from "@/features/filmClones/queries";
import type { FilmClone } from "@/features/filmClones/types";

interface RelocalizeButtonProps {
  clone: Pick<FilmClone, "id" | "hasOpenRequests">;
}

export function RelocalizeButton({ clone }: RelocalizeButtonProps) {
  const relocalizeMutation = useRelocalizeFilmCloneMutation();

  function handleRelocalize() {
    if (!window.confirm(RELOCALIZE_CONFIRMATION)) return;
    relocalizeMutation.mutate(clone.id);
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="self-start">
        <Button
          variant="secondary"
          disabled={clone.hasOpenRequests || relocalizeMutation.isPending}
          onClick={handleRelocalize}
        >
          Back to localization
        </Button>
      </div>
      {relocalizeMutation.isError && <ErrorAlert>{relocalizeMutation.error.message}</ErrorAlert>}
    </div>
  );
}
