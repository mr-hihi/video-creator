"use client";

import { useState } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { TextInput } from "@/components/atoms/TextInput";
import { EMPTY_VALUE_LABEL, ENTITY_TYPE_LABELS, SEARCH_BY_NAME_PLACEHOLDER } from "@/features/films/constants";
import { useFilmCharactersQuery, useLinkProjectCharacterMutation } from "@/features/films/queries";
import type { FilmProjectDetail } from "@/features/films/types";

interface FilmCastPickerProps {
  project: FilmProjectDetail;
  isReadOnly: boolean;
  onClose: () => void;
}

export function FilmCastPicker({ project, isReadOnly, onClose }: FilmCastPickerProps) {
  const charactersQuery = useFilmCharactersQuery();
  const linkCharacterMutation = useLinkProjectCharacterMutation();
  const [searchText, setSearchText] = useState("");

  const linkedCharacterIds = new Set(project.characters.map((character) => character.id));
  const normalizedSearchText = searchText.trim().toLowerCase();
  const unlinkedCharacters = (charactersQuery.data ?? []).filter(
    (character) =>
      !linkedCharacterIds.has(character.id) && character.name.toLowerCase().includes(normalizedSearchText),
  );

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-border p-4">
      <h3 className="text-base font-semibold">Add from library</h3>
      <TextInput
        type="text"
        value={searchText}
        placeholder={SEARCH_BY_NAME_PLACEHOLDER}
        aria-label="Search the library"
        autoComplete="off"
        onChange={(event) => setSearchText(event.target.value)}
      />
      {charactersQuery.isError && <ErrorAlert>{charactersQuery.error.message}</ErrorAlert>}
      {unlinkedCharacters.length ? (
        <ul className="flex max-h-64 flex-col divide-y divide-border overflow-y-auto">
          {unlinkedCharacters.map((character) => (
            <li key={character.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span className="min-w-0 text-sm break-words">
                {character.name} <span className="text-xs text-muted">· {ENTITY_TYPE_LABELS[character.entityType]}</span>
              </span>
              <Button
                variant="secondary"
                disabled={isReadOnly || linkCharacterMutation.isPending}
                onClick={() => linkCharacterMutation.mutate({ projectId: project.id, characterId: character.id })}
              >
                Add
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">{EMPTY_VALUE_LABEL}</p>
      )}
      {linkCharacterMutation.isError && <ErrorAlert>{linkCharacterMutation.error.message}</ErrorAlert>}
      <div className="self-start">
        <Button variant="secondary" onClick={onClose}>
          Done
        </Button>
      </div>
    </section>
  );
}
