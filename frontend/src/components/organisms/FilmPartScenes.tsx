"use client";

import { Fragment, useState } from "react";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { useFilmPartQuery } from "@/features/films/queries";
import type { EpisodeDetail, EpisodePartWithCounts, FilmProjectDetail } from "@/features/films/types";
import {
  charactersToOptions,
  countScenesBeforePart,
  isFilmEpisodeBusy,
  toSceneNumber,
} from "@/features/films/utils";
import { FilmSceneCard } from "./FilmSceneCard";
import { NewFilmSceneCard } from "./NewFilmSceneCard";

interface NewSceneSlot {
  afterPosition: number | undefined;
}

interface FilmPartScenesProps {
  project: FilmProjectDetail;
  episode: EpisodeDetail;
  part: EpisodePartWithCounts;
  isLocked: boolean;
}

export function FilmPartScenes({ project, episode, part, isLocked }: FilmPartScenesProps) {
  const partQuery = useFilmPartQuery(part.id, isFilmEpisodeBusy(episode));
  const [newSceneSlot, setNewSceneSlot] = useState<NewSceneSlot>();

  if (partQuery.isPending) return <PlaceholderMessage>Loading scenes…</PlaceholderMessage>;
  if (partQuery.isError) return <ErrorAlert>{partQuery.error.message}</ErrorAlert>;

  const { scenes, openRequests } = partQuery.data;
  const scenesBeforePart = countScenesBeforePart(episode.parts, part.position);
  const castOptions = charactersToOptions(project.characters);
  const isNewSceneAtEnd = newSceneSlot !== undefined && newSceneSlot.afterPosition === undefined;

  function renderNewSceneCard(afterPosition: number | undefined) {
    return (
      <NewFilmSceneCard
        episodeId={episode.id}
        partId={part.id}
        afterPosition={afterPosition}
        defaultClipDurationS={project.clipDurationS}
        castOptions={castOptions}
        isLocked={isLocked}
        onClose={() => setNewSceneSlot(undefined)}
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {scenes.map((scene) => (
        <Fragment key={scene.id}>
          <FilmSceneCard
            scene={scene}
            sceneNumber={toSceneNumber(scene, scenesBeforePart)}
            sceneCount={scenes.length}
            project={project}
            openRequests={openRequests}
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
  );
}
