import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { CopyButton } from "@/components/molecules/CopyButton";
import type { FilmCloneDetail } from "@/features/filmClones/types";
import { buildScriptMarkdown, canRelocalizeFilmClone, describeMissingCloneContent } from "@/features/filmClones/utils";
import { CloneSceneCard } from "./CloneSceneCard";
import { RelocalizeButton } from "./RelocalizeButton";

interface CloneScriptTabProps {
  clone: FilmCloneDetail;
}

export function CloneScriptTab({ clone }: CloneScriptTabProps) {
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
        <PlaceholderMessage>{describeMissingCloneContent(clone)}</PlaceholderMessage>
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
