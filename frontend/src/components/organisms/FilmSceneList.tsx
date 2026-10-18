"use client";

import { Fragment, useState } from "react";
import { Button } from "@/components/atoms/Button";
import { Panel } from "@/components/atoms/Panel";
import { STOP_TO_EDIT_HINT } from "@/features/films/constants";
import type { EpisodeDetail, FilmProjectDetail } from "@/features/films/types";
import { charactersToOptions } from "@/features/films/utils";
import { FilmSceneCard } from "./FilmSceneCard";
import { NewFilmSceneCard } from "./NewFilmSceneCard";

interface NewSceneSlot {
  afterPosition: number | undefined;
}

interface FilmSceneListProps {
  project: FilmProjectDetail;
  episode: EpisodeDetail;
}

export function FilmSceneList({ project, episode }: FilmSceneListProps) {
  const [newSceneSlot, setNewSceneSlot] = useState<NewSceneSlot>();
  const isRunning = episode.status === "running";
  const isLocked = project.status === "archived" || isRunning;
  const castOptions = charactersToOptions(project.characters);
  const isNewSceneAtEnd = newSceneSlot !== undefined && newSceneSlot.afterPosition === undefined;

  function renderNewSceneCard(afterPosition: number | undefined) {
    return (
      <NewFilmSceneCard
        episodeId={episode.id}
        afterPosition={afterPosition}
        defaultClipDurationS={project.clipDurationS}
        castOptions={castOptions}
        isLocked={isLocked}
        onClose={() => setNewSceneSlot(undefined)}
      />
    );
  }

  return (
    <Panel title="Scenes">
      <div className="flex flex-col gap-4">
        {isRunning && <p className="text-sm text-muted">{STOP_TO_EDIT_HINT}</p>}
        {episode.scenes.map((scene) => (
          <Fragment key={scene.id}>
            <FilmSceneCard
              scene={scene}
              sceneCount={episode.scenes.length}
              project={project}
              episode={episode}
              castOptions={castOptions}
              isLocked={isLocked}
              isInsertDisabled={newSceneSlot !== undefined}
              onInsertAfter={() => setNewSceneSlot({ afterPosition: scene.position })}
            />
            {newSceneSlot?.afterPosition === scene.position && renderNewSceneCard(scene.position)}
          </Fragment>
        ))}
        {isNewSceneAtEnd && renderNewSceneCard(undefined)}
        <div className="self-start">
          <Button
            variant="secondary"
            disabled={isLocked || newSceneSlot !== undefined}
            onClick={() => setNewSceneSlot({ afterPosition: undefined })}
          >
            Add scene
          </Button>
        </div>
      </div>
    </Panel>
  );
}
