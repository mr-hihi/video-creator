"use client";

import { useState } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { EMPTY_VALUE_LABEL } from "@/features/films/constants";
import { useGenerateMissingReferencesMutation, useLinkProjectCharacterMutation } from "@/features/films/queries";
import type { FilmCharacter, FilmProjectDetail } from "@/features/films/types";
import { countMissingReferences } from "@/features/films/utils";
import { FilmCastCard } from "./FilmCastCard";
import { FilmCastPicker } from "./FilmCastPicker";
import { FilmCharacterForm } from "./FilmCharacterForm";

type CastEditor = "picker" | "newCharacter";

interface FilmProjectCastProps {
  project: FilmProjectDetail;
  isReadOnly: boolean;
}

export function FilmProjectCast({ project, isReadOnly }: FilmProjectCastProps) {
  const [openEditor, setOpenEditor] = useState<CastEditor>();
  const generateMissingMutation = useGenerateMissingReferencesMutation();
  const linkCharacterMutation = useLinkProjectCharacterMutation();
  const missingReferenceCount = countMissingReferences(project.characters);
  const mutationError = generateMissingMutation.error ?? linkCharacterMutation.error;

  function linkNewCharacter(character: FilmCharacter) {
    linkCharacterMutation.mutate(
      { projectId: project.id, characterId: character.id },
      { onSuccess: () => setOpenEditor(undefined) },
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {project.characters.length ? (
        <ul className="grid gap-4 sm:grid-cols-2">
          {project.characters.map((character) => (
            <FilmCastCard key={character.id} character={character} project={project} isReadOnly={isReadOnly} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">{EMPTY_VALUE_LABEL}</p>
      )}
      {mutationError && <ErrorAlert>{mutationError.message}</ErrorAlert>}
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" disabled={isReadOnly || openEditor !== undefined} onClick={() => setOpenEditor("picker")}>
          Add from library
        </Button>
        <Button
          variant="secondary"
          disabled={isReadOnly || openEditor !== undefined}
          onClick={() => setOpenEditor("newCharacter")}
        >
          New character
        </Button>
        <Button
          disabled={isReadOnly || missingReferenceCount === 0 || generateMissingMutation.isPending}
          onClick={() => generateMissingMutation.mutate(project.id)}
        >
          Generate missing references ({missingReferenceCount})
        </Button>
      </div>
      {openEditor === "picker" && (
        <FilmCastPicker project={project} isReadOnly={isReadOnly} onClose={() => setOpenEditor(undefined)} />
      )}
      {openEditor === "newCharacter" && (
        <section className="flex flex-col gap-3 rounded-lg border border-border p-4">
          <h3 className="text-base font-semibold">New character</h3>
          <FilmCharacterForm
            character={undefined}
            isReadOnly={isReadOnly || linkCharacterMutation.isPending}
            onSaved={linkNewCharacter}
            onClose={() => setOpenEditor(undefined)}
          />
        </section>
      )}
    </div>
  );
}
