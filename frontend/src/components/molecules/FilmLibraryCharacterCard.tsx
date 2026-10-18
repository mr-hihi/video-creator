import { AspectImage } from "@/components/atoms/AspectImage";
import { EMPTY_VALUE_LABEL, ENTITY_TYPE_LABELS } from "@/features/films/constants";
import type { FilmCharacter } from "@/features/films/types";
import { buildFilmFileUrl, describeCount, entityTypeToOrientation } from "@/features/films/utils";

interface FilmLibraryCharacterCardProps {
  character: FilmCharacter;
  isSelected: boolean;
  onOpen: (character: FilmCharacter) => void;
}

export function FilmLibraryCharacterCard({ character, isSelected, onOpen }: FilmLibraryCharacterCardProps) {
  const referenceUrl = character.referencePath
    ? buildFilmFileUrl(character.referencePath, character.updatedAt)
    : undefined;

  return (
    <li>
      <button
        type="button"
        aria-pressed={isSelected}
        onClick={() => onOpen(character)}
        className={`flex w-full min-w-0 flex-col gap-2 rounded-lg border p-3 text-left transition-colors hover:border-accent/60 focus-visible:outline-2 focus-visible:outline-accent ${
          isSelected ? "border-accent" : "border-border"
        }`}
      >
        <AspectImage
          src={referenceUrl}
          alt={`${character.name} reference`}
          orientation={entityTypeToOrientation(character.entityType)}
          fallbackText={EMPTY_VALUE_LABEL}
        />
        <span className="text-sm font-semibold break-words">{character.name}</span>
        <span className="text-xs text-muted">
          {ENTITY_TYPE_LABELS[character.entityType]} · {character.styleName} ·{" "}
          {describeCount(character.projectCount, "projects")}
        </span>
      </button>
    </li>
  );
}
