"use client";

import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { FilmCloneListItem } from "@/components/molecules/FilmCloneListItem";
import { DELETE_CLONE_CONFIRMATION } from "@/features/filmClones/constants";
import { useDeleteFilmCloneMutation, useFilmClonesQuery } from "@/features/filmClones/queries";

export function FilmCloneHistory() {
  const clonesQuery = useFilmClonesQuery();
  const deleteCloneMutation = useDeleteFilmCloneMutation();

  function handleDelete(cloneId: string) {
    if (!window.confirm(DELETE_CLONE_CONFIRMATION)) return;
    deleteCloneMutation.mutate(cloneId);
  }

  if (clonesQuery.isPending) return <PlaceholderMessage>Loading clones…</PlaceholderMessage>;
  if (clonesQuery.isError) return <ErrorAlert>{clonesQuery.error.message}</ErrorAlert>;
  if (clonesQuery.data.length === 0) return <PlaceholderMessage>No clones yet</PlaceholderMessage>;

  return (
    <div className="flex flex-col gap-3">
      {deleteCloneMutation.isError && <ErrorAlert>{deleteCloneMutation.error.message}</ErrorAlert>}
      <ul className="divide-y divide-border">
        {clonesQuery.data.map((clone) => (
          <FilmCloneListItem
            key={clone.id}
            clone={clone}
            isDeleting={deleteCloneMutation.isPending}
            onDelete={handleDelete}
          />
        ))}
      </ul>
    </div>
  );
}
