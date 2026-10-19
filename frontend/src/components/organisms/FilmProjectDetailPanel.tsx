"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/atoms/Badge";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { InfoNotice } from "@/components/atoms/InfoNotice";
import { Panel } from "@/components/atoms/Panel";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { TabList } from "@/components/atoms/TabList";
import {
  ARCHIVED_BADGE_LABEL,
  ARCHIVED_NOTICE,
  FILMS_PATH,
  OVERVIEW_PROJECT_TAB,
  PROJECT_TAB_OPTIONS,
  STORY_BIBLE_PROJECT_TAB,
  type ProjectTab,
} from "@/features/films/constants";
import {
  useArchiveFilmProjectMutation,
  useDeleteFilmProjectMutation,
  useFilmProjectQuery,
  useUnarchiveFilmProjectMutation,
} from "@/features/films/queries";
import type { FilmProjectDetail } from "@/features/films/types";
import { buildDeleteProjectConfirmation, buildFilmProjectTabPath, resolveProjectTab } from "@/features/films/utils";
import { isNotFoundError } from "@/lib/api/client";
import { UNSAVED_CHANGES_CONFIRMATION, UnsavedChangesContext, useUnsavedPageChanges } from "@/lib/unsavedChanges";
import { FilmProjectCast } from "./FilmProjectCast";
import { FilmProjectEpisodes } from "./FilmProjectEpisodes";
import { FilmProjectSettingsForm } from "./FilmProjectSettingsForm";
import { FilmStoryBibleForm } from "./FilmStoryBibleForm";

interface FilmProjectDetailPanelProps {
  projectId: string;
  requestedTab: string | undefined;
}

export function FilmProjectDetailPanel({ projectId, requestedTab }: FilmProjectDetailPanelProps) {
  const projectQuery = useFilmProjectQuery(projectId);

  if (projectQuery.isPending) return <PlaceholderMessage>Loading project…</PlaceholderMessage>;
  if (isNotFoundError(projectQuery.error)) return <ProjectNotFound />;
  if (projectQuery.isError) return <ErrorAlert>{projectQuery.error.message}</ErrorAlert>;
  return <FilmProjectDetailContent project={projectQuery.data} requestedTab={requestedTab} />;
}

function ProjectNotFound() {
  return (
    <div className="flex flex-col items-center gap-2">
      <PlaceholderMessage>Project not found</PlaceholderMessage>
      <Link href={FILMS_PATH} className="text-sm text-accent hover:underline">
        Back to Film Studio
      </Link>
    </div>
  );
}

interface FilmProjectDetailContentProps {
  project: FilmProjectDetail;
  requestedTab: string | undefined;
}

function FilmProjectDetailContent({ project, requestedTab }: FilmProjectDetailContentProps) {
  const router = useRouter();
  const { hasUnsavedChanges, reportUnsavedChanges } = useUnsavedPageChanges();
  const selectedTab = resolveProjectTab(requestedTab);
  const isReadOnly = project.status === "archived";

  function selectTab(tab: ProjectTab) {
    if (tab === selectedTab) return;
    if (hasUnsavedChanges && !window.confirm(UNSAVED_CHANGES_CONFIRMATION)) return;
    router.replace(buildFilmProjectTabPath(project.id, tab), { scroll: false });
  }

  return (
    <div className="flex flex-col gap-6">
      <FilmProjectHeader project={project} />
      {isReadOnly && <InfoNotice>{ARCHIVED_NOTICE}</InfoNotice>}
      <TabList label="Project" value={selectedTab} tabs={PROJECT_TAB_OPTIONS} onChange={selectTab} />
      {selectedTab === OVERVIEW_PROJECT_TAB && (
        <>
          <div className="grid items-start gap-6 lg:grid-cols-2">
            <Panel title="Settings">
              <FilmProjectSettingsForm project={project} isReadOnly={isReadOnly} />
            </Panel>
            <Panel title="Cast">
              <FilmProjectCast project={project} isReadOnly={isReadOnly} />
            </Panel>
          </div>
          <FilmProjectEpisodes project={project} isReadOnly={isReadOnly} />
        </>
      )}
      {selectedTab === STORY_BIBLE_PROJECT_TAB && (
        <UnsavedChangesContext value={reportUnsavedChanges}>
          <FilmStoryBibleForm project={project} isReadOnly={isReadOnly} />
        </UnsavedChangesContext>
      )}
    </div>
  );
}

function FilmProjectHeader({ project }: { project: FilmProjectDetail }) {
  const router = useRouter();
  const archiveMutation = useArchiveFilmProjectMutation();
  const unarchiveMutation = useUnarchiveFilmProjectMutation();
  const deleteMutation = useDeleteFilmProjectMutation(() => router.push(FILMS_PATH));
  const isArchived = project.status === "archived";
  const isBusy = archiveMutation.isPending || unarchiveMutation.isPending || deleteMutation.isPending;
  const mutationError = archiveMutation.error ?? unarchiveMutation.error ?? deleteMutation.error;

  function handleDelete() {
    if (!window.confirm(buildDeleteProjectConfirmation(project.name))) return;
    deleteMutation.mutate(project.id);
  }

  return (
    <Panel
      title={project.name}
      headerAction={
        <div className="flex flex-wrap items-center gap-2">
          {isArchived && <Badge tone="neutral">{ARCHIVED_BADGE_LABEL}</Badge>}
          {isArchived ? (
            <Button variant="secondary" disabled={isBusy} onClick={() => unarchiveMutation.mutate(project.id)}>
              Unarchive
            </Button>
          ) : (
            <Button variant="secondary" disabled={isBusy} onClick={() => archiveMutation.mutate(project.id)}>
              Archive
            </Button>
          )}
          <Button variant="secondary" disabled={isBusy} onClick={handleDelete}>
            Delete
          </Button>
        </div>
      }
    >
      {mutationError && <ErrorAlert>{mutationError.message}</ErrorAlert>}
    </Panel>
  );
}
