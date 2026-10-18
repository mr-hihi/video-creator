"use client";

import { useState } from "react";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { SegmentedControl } from "@/components/atoms/SegmentedControl";
import { FilmProjectListItem } from "@/components/molecules/FilmProjectListItem";
import {
  DEFAULT_PROJECT_STATUS,
  EMPTY_PROJECTS_MESSAGES,
  PROJECT_STATUS_OPTIONS,
} from "@/features/films/constants";
import { useFilmProjectsQuery } from "@/features/films/queries";
import type { ProjectStatus } from "@/features/films/types";

export function FilmProjectList() {
  const [status, setStatus] = useState<ProjectStatus>(DEFAULT_PROJECT_STATUS);

  return (
    <div className="flex flex-col gap-4">
      <SegmentedControl<ProjectStatus>
        label="Project status"
        value={status}
        options={PROJECT_STATUS_OPTIONS}
        onChange={setStatus}
      />
      <FilmProjectRows status={status} />
    </div>
  );
}

function FilmProjectRows({ status }: { status: ProjectStatus }) {
  const projectsQuery = useFilmProjectsQuery(status);

  if (projectsQuery.isPending) return <PlaceholderMessage>Loading projects…</PlaceholderMessage>;
  if (projectsQuery.isError) return <ErrorAlert>{projectsQuery.error.message}</ErrorAlert>;
  if (!projectsQuery.data.length) return <PlaceholderMessage>{EMPTY_PROJECTS_MESSAGES[status]}</PlaceholderMessage>;
  return (
    <ul className="divide-y divide-border">
      {projectsQuery.data.map((project) => (
        <FilmProjectListItem key={project.id} project={project} />
      ))}
    </ul>
  );
}
