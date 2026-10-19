import { Button } from "@/components/atoms/Button";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { CopyButton } from "@/components/molecules/CopyButton";
import { OPEN_LOCALIZATION_LABEL } from "@/features/filmClones/constants";
import type { FilmCloneDetail } from "@/features/filmClones/types";
import {
  buildScriptMarkdown,
  canRelocalizeFilmClone,
  describeFilmCloneStep,
  describeMissingCloneContent,
} from "@/features/filmClones/utils";
import { CloneSceneCard } from "./CloneSceneCard";
import { RelocalizeButton } from "./RelocalizeButton";

interface CloneScriptTabProps {
  clone: FilmCloneDetail;
  onOpenLocalization: () => void;
}

export function CloneScriptTab({ clone, onOpenLocalization }: CloneScriptTabProps) {
  const hasScenes = clone.scenes.length > 0;
  const shotsById = new Map(clone.shots.map((shot) => [shot.id, shot]));

  return (
    <div className="flex flex-col gap-6">
      {hasScenes ? (
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 flex-1 basis-64 flex-col gap-1">
            <h3 className="text-xl font-semibold break-words">{clone.scriptTitle}</h3>
            {clone.logline && <p className="text-sm break-words text-muted">{clone.logline}</p>}
          </div>
          <CopyButton text={buildScriptMarkdown(clone)} label="Copy script" />
        </header>
      ) : (
        <ScriptPlaceholder clone={clone} onOpenLocalization={onOpenLocalization} />
      )}
      {canRelocalizeFilmClone(clone) && <RelocalizeButton clone={clone} />}
      {hasScenes && (
        <ol className="flex flex-col gap-4">
          {clone.scenes.map((scene) => (
            <li key={scene.id}>
              <CloneSceneCard scene={scene} shot={shotsById.get(scene.shotId)} clone={clone} />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function ScriptPlaceholder({ clone, onOpenLocalization }: CloneScriptTabProps) {
  if (clone.status !== "waiting") return <PlaceholderMessage>{describeMissingCloneContent(clone)}</PlaceholderMessage>;
  return (
    <div className="flex flex-col items-center gap-2">
      <PlaceholderMessage>{describeFilmCloneStep(clone)}</PlaceholderMessage>
      <Button variant="secondary" onClick={onOpenLocalization}>
        {OPEN_LOCALIZATION_LABEL}
      </Button>
    </div>
  );
}
