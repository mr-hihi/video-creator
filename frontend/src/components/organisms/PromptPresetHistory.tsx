"use client";

import { useState } from "react";
import { Badge } from "@/components/atoms/Badge";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { PromptsUsedList } from "@/components/molecules/PromptsUsedList";
import { CURRENT_VERSION_BADGE_LABEL } from "@/features/promptPresets/constants";
import {
  usePromptPresetVersionQuery,
  usePromptPresetVersionsQuery,
  useRestorePromptPresetVersionMutation,
} from "@/features/promptPresets/queries";
import { describePresetChange } from "@/features/promptPresets/utils";
import { formatDateTime } from "@/lib/format";

const SELECTED_VERSION_CLASS_NAME = "border-accent bg-accent/5";
const UNSELECTED_VERSION_CLASS_NAME = "border-transparent hover:bg-foreground/5";

interface PromptPresetHistoryProps {
  presetId: string;
  currentVersion: number;
  onRestored: (notice: string) => void;
}

export function PromptPresetHistory({ presetId, currentVersion, onRestored }: PromptPresetHistoryProps) {
  const versionsQuery = usePromptPresetVersionsQuery(presetId);
  const [selectedVersion, setSelectedVersion] = useState<number>();

  if (versionsQuery.isPending) return <PlaceholderMessage>Loading history…</PlaceholderMessage>;
  if (versionsQuery.isError) return <ErrorAlert>{versionsQuery.error.message}</ErrorAlert>;

  return (
    <section className="flex flex-col gap-4 rounded-lg border border-border bg-background p-4">
      <h3 className="text-base font-semibold">History</h3>
      <ul className="flex flex-col gap-1">
        {versionsQuery.data.map((version) => (
          <li key={version.version}>
            <button
              type="button"
              aria-current={version.version === selectedVersion ? "true" : undefined}
              onClick={() => setSelectedVersion(version.version)}
              className={`flex w-full flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border px-3 py-2 text-left text-sm transition-colors focus-visible:outline-2 focus-visible:outline-accent ${
                version.version === selectedVersion ? SELECTED_VERSION_CLASS_NAME : UNSELECTED_VERSION_CLASS_NAME
              }`}
            >
              <span className="font-medium">v{version.version}</span>
              <time dateTime={version.createdAt} className="text-muted">
                {formatDateTime(version.createdAt)}
              </time>
              <span>{describePresetChange(version)}</span>
              {version.version === currentVersion && <Badge tone="success">{CURRENT_VERSION_BADGE_LABEL}</Badge>}
            </button>
          </li>
        ))}
      </ul>
      {selectedVersion !== undefined && (
        <PresetVersionView
          key={selectedVersion}
          presetId={presetId}
          version={selectedVersion}
          isCurrent={selectedVersion === currentVersion}
          onRestored={onRestored}
        />
      )}
    </section>
  );
}

interface PresetVersionViewProps {
  presetId: string;
  version: number;
  isCurrent: boolean;
  onRestored: (notice: string) => void;
}

function PresetVersionView({ presetId, version, isCurrent, onRestored }: PresetVersionViewProps) {
  const versionQuery = usePromptPresetVersionQuery(presetId, version);
  const restoreMutation = useRestorePromptPresetVersionMutation((restoredPreset) =>
    onRestored(`Restored v${version} as v${restoredPreset.currentVersion}`),
  );

  function restore() {
    restoreMutation.mutate({ presetId, version });
  }

  if (versionQuery.isPending) return <PlaceholderMessage>Loading v{version}…</PlaceholderMessage>;
  if (versionQuery.isError) return <ErrorAlert>{versionQuery.error.message}</ErrorAlert>;

  return (
    <div className="flex flex-col gap-4">
      {!isCurrent && (
        <Button disabled={restoreMutation.isPending} onClick={restore}>
          Restore v{version}
        </Button>
      )}
      {restoreMutation.isError && <ErrorAlert>{restoreMutation.error.message}</ErrorAlert>}
      <PromptsUsedList prompts={versionQuery.data.prompts} />
    </div>
  );
}
