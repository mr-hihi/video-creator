"use client";

import { useState } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { Panel } from "@/components/atoms/Panel";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { FilmLibraryCharacterCard } from "@/components/molecules/FilmLibraryCharacterCard";
import { SelectField } from "@/components/molecules/SelectField";
import { TextField } from "@/components/molecules/TextField";
import { labelsToSelectOptions } from "@/features/filmClones/utils";
import {
  ALL_ENTITY_TYPES_LABEL,
  ALL_ENTITY_TYPES_VALUE,
  CHARACTERS_LIBRARY_HINT,
  EMPTY_VALUE_LABEL,
  ENTITY_TYPE_LABELS,
  SEARCH_BY_NAME_PLACEHOLDER,
} from "@/features/films/constants";
import { useFilmCharactersQuery } from "@/features/films/queries";
import type { EntityType, FilmCharacter } from "@/features/films/types";
import { FilmCharacterForm } from "./FilmCharacterForm";

type EntityTypeFilter = EntityType | typeof ALL_ENTITY_TYPES_VALUE;

const ENTITY_TYPE_FILTER_OPTIONS: readonly { value: EntityTypeFilter; label: string }[] = [
  { value: ALL_ENTITY_TYPES_VALUE, label: ALL_ENTITY_TYPES_LABEL },
  ...labelsToSelectOptions(ENTITY_TYPE_LABELS),
];

type OpenCharacterForm = { kind: "new" } | { kind: "edit"; characterId: string };

export function FilmCharacterLibrary() {
  const charactersQuery = useFilmCharactersQuery();
  const [searchText, setSearchText] = useState("");
  const [typeFilter, setTypeFilter] = useState<EntityTypeFilter>(ALL_ENTITY_TYPES_VALUE);
  const [openForm, setOpenForm] = useState<OpenCharacterForm>();

  const characters = charactersQuery.data ?? [];
  const normalizedSearchText = searchText.trim().toLowerCase();
  const matchingCharacters = characters.filter(
    (character) =>
      character.name.toLowerCase().includes(normalizedSearchText) &&
      (typeFilter === ALL_ENTITY_TYPES_VALUE || character.entityType === typeFilter),
  );
  const editedCharacter =
    openForm?.kind === "edit" ? characters.find((character) => character.id === openForm.characterId) : undefined;
  const isFormOpen = openForm?.kind === "new" || editedCharacter !== undefined;

  function openCharacter(character: FilmCharacter) {
    setOpenForm({ kind: "edit", characterId: character.id });
  }

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <Panel
        title="Characters"
        headerAction={
          <Button disabled={openForm?.kind === "new"} onClick={() => setOpenForm({ kind: "new" })}>
            New character
          </Button>
        }
      >
        <div className="flex flex-col gap-4">
          <p className="text-sm text-muted">{CHARACTERS_LIBRARY_HINT}</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <TextField label="Search" value={searchText} placeholder={SEARCH_BY_NAME_PLACEHOLDER} onChange={setSearchText} />
            <SelectField<EntityTypeFilter>
              label="Type"
              value={typeFilter}
              options={ENTITY_TYPE_FILTER_OPTIONS}
              onChange={setTypeFilter}
            />
          </div>
          {charactersQuery.isPending && <PlaceholderMessage>Loading characters…</PlaceholderMessage>}
          {charactersQuery.isError && <ErrorAlert>{charactersQuery.error.message}</ErrorAlert>}
          {charactersQuery.isSuccess && !matchingCharacters.length && <PlaceholderMessage>{EMPTY_VALUE_LABEL}</PlaceholderMessage>}
          {matchingCharacters.length > 0 && (
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {matchingCharacters.map((character) => (
                <FilmLibraryCharacterCard
                  key={character.id}
                  character={character}
                  isSelected={character.id === editedCharacter?.id}
                  onOpen={openCharacter}
                />
              ))}
            </ul>
          )}
        </div>
      </Panel>
      {isFormOpen && (
        <Panel title={editedCharacter ? editedCharacter.name : "New character"}>
          <FilmCharacterForm
            key={editedCharacter?.id ?? "new"}
            character={editedCharacter}
            isReadOnly={false}
            onSaved={() => setOpenForm(undefined)}
            onClose={() => setOpenForm(undefined)}
          />
        </Panel>
      )}
    </div>
  );
}
