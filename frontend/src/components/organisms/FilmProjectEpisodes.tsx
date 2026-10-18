"use client";

import { useState } from "react";
import { Button } from "@/components/atoms/Button";
import { Panel } from "@/components/atoms/Panel";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { FilmEpisodeListItem } from "@/components/molecules/FilmEpisodeListItem";
import type { FilmProjectDetail } from "@/features/films/types";
import { NewFilmEpisodeForm } from "./NewFilmEpisodeForm";

interface FilmProjectEpisodesProps {
  project: FilmProjectDetail;
  isReadOnly: boolean;
}

export function FilmProjectEpisodes({ project, isReadOnly }: FilmProjectEpisodesProps) {
  const [isNewEpisodeOpen, setIsNewEpisodeOpen] = useState(false);

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <Panel
        title="Episodes"
        headerAction={
          <Button disabled={isReadOnly || isNewEpisodeOpen} onClick={() => setIsNewEpisodeOpen(true)}>
            New episode
          </Button>
        }
      >
        {project.episodes.length ? (
          <ul className="divide-y divide-border">
            {project.episodes.map((episode) => (
              <FilmEpisodeListItem key={episode.id} episode={episode} />
            ))}
          </ul>
        ) : (
          <PlaceholderMessage>No episodes yet</PlaceholderMessage>
        )}
      </Panel>
      {isNewEpisodeOpen && (
        <Panel title="New episode">
          <NewFilmEpisodeForm project={project} isReadOnly={isReadOnly} />
        </Panel>
      )}
    </div>
  );
}
