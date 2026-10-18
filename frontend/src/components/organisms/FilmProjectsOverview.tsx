"use client";

import { useState } from "react";
import { Button } from "@/components/atoms/Button";
import { Panel } from "@/components/atoms/Panel";
import { FilmProjectList } from "./FilmProjectList";
import { NewFilmProjectForm } from "./NewFilmProjectForm";

export function FilmProjectsOverview() {
  const [isNewProjectOpen, setIsNewProjectOpen] = useState(false);

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <Panel
        title="Projects"
        headerAction={
          <Button disabled={isNewProjectOpen} onClick={() => setIsNewProjectOpen(true)}>
            New project
          </Button>
        }
      >
        <FilmProjectList />
      </Panel>
      {isNewProjectOpen && (
        <Panel title="New project">
          <NewFilmProjectForm onCancel={() => setIsNewProjectOpen(false)} />
        </Panel>
      )}
    </div>
  );
}
