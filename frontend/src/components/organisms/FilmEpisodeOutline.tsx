"use client";

import { Fragment, useState } from "react";
import { Button } from "@/components/atoms/Button";
import { Panel } from "@/components/atoms/Panel";
import { STOP_TO_EDIT_HINT } from "@/features/films/constants";
import type { EpisodeDetail, FilmProjectDetail } from "@/features/films/types";
import { FilmPartBlock } from "./FilmPartBlock";
import { NewFilmPartForm } from "./NewFilmPartForm";

const NO_OPEN_PART_IDS: ReadonlySet<string> = new Set();

interface NewPartSlot {
  afterPosition: number | undefined;
}

interface FilmEpisodeOutlineProps {
  project: FilmProjectDetail;
  episode: EpisodeDetail;
}

export function FilmEpisodeOutline({ project, episode }: FilmEpisodeOutlineProps) {
  const [openPartIds, setOpenPartIds] = useState(NO_OPEN_PART_IDS);
  const [newPartSlot, setNewPartSlot] = useState<NewPartSlot>();
  const isRunning = episode.status === "running";
  const isLocked = project.status === "archived" || isRunning;
  const isNewPartAtEnd = newPartSlot !== undefined && newPartSlot.afterPosition === undefined;

  function togglePart(partId: string) {
    setOpenPartIds((currentPartIds) => {
      const nextPartIds = new Set(currentPartIds);
      if (!nextPartIds.delete(partId)) nextPartIds.add(partId);
      return nextPartIds;
    });
  }

  function renderNewPartForm(afterPosition: number | undefined) {
    return (
      <NewFilmPartForm
        episodeId={episode.id}
        afterPosition={afterPosition}
        isLocked={isLocked}
        onClose={() => setNewPartSlot(undefined)}
      />
    );
  }

  return (
    <Panel title="Outline">
      <div className="flex flex-col gap-4">
        {isRunning && <p className="text-sm text-muted">{STOP_TO_EDIT_HINT}</p>}
        {episode.parts.map((part) => (
          <Fragment key={part.id}>
            <FilmPartBlock
              project={project}
              episode={episode}
              part={part}
              isOpen={openPartIds.has(part.id)}
              isLocked={isLocked}
              isInsertDisabled={newPartSlot !== undefined}
              onToggle={() => togglePart(part.id)}
              onInsertAfter={() => setNewPartSlot({ afterPosition: part.position })}
            />
            {newPartSlot?.afterPosition === part.position && renderNewPartForm(part.position)}
          </Fragment>
        ))}
        {isNewPartAtEnd && renderNewPartForm(undefined)}
        <div className="self-start">
          <Button
            variant="secondary"
            disabled={isLocked || newPartSlot !== undefined}
            onClick={() => setNewPartSlot({ afterPosition: undefined })}
          >
            Add part
          </Button>
        </div>
      </div>
    </Panel>
  );
}
