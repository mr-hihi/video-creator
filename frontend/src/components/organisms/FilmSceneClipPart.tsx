"use client";

import { useState } from "react";
import { AspectImage } from "@/components/atoms/AspectImage";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { VideoPlayer } from "@/components/atoms/VideoPlayer";
import { FilmScenePart } from "@/components/molecules/FilmScenePart";
import { TextField } from "@/components/molecules/TextField";
import type { GenerationRequest } from "@/features/filmClones/types";
import { MEDIA_STATUS_SEPARATOR } from "@/features/films/constants";
import { useGenerateSceneMediaMutation, useUpdateFilmSceneMutation } from "@/features/films/queries";
import type { Orientation, Scene, TrimDraft } from "@/features/films/types";
import {
  buildFilmFileUrl,
  describeBusyMedia,
  describeGenerateLabel,
  findQueuedRequest,
  findSceneSegmentLabel,
  findSettledMediaError,
  sceneToTrimDraft,
  secondsTextToMs,
  toSceneNumber,
} from "@/features/films/utils";
import { MISSING_OUTPUT_MESSAGE } from "@/features/jobs/constants";
import { FilmCancelRequestButton } from "./FilmCancelRequestButton";

interface FilmSceneClipPartProps {
  scene: Scene;
  openRequests: readonly GenerationRequest[];
  orientation: Orientation;
  isLocked: boolean;
  isSceneBusy: boolean;
}

export function FilmSceneClipPart({ scene, openRequests, orientation, isLocked, isSceneBusy }: FilmSceneClipPartProps) {
  const generateClipMutation = useGenerateSceneMediaMutation();
  const [trimDraft, setTrimDraft] = useState<TrimDraft>();

  const clipLabel = `Scene ${toSceneNumber(scene)} clip`;
  const busyLabel = describeBusyMedia(scene.clipStatus);
  const statusParts = [busyLabel, findSceneSegmentLabel(scene.id, openRequests)].filter(Boolean);
  const isActionLocked = isLocked || isSceneBusy || generateClipMutation.isPending;
  const queuedRequest = findQueuedRequest(
    openRequests,
    (request) => request.sceneId === scene.id && request.kind === "scene_clip",
  );

  return (
    <FilmScenePart
      title="Clip"
      media={
        scene.clipPath ? (
          <VideoPlayer src={buildFilmFileUrl(scene.clipPath, scene.updatedAt)} label={clipLabel} orientation={orientation} />
        ) : (
          <AspectImage src={undefined} alt={clipLabel} orientation={orientation} fallbackText={busyLabel ?? MISSING_OUTPUT_MESSAGE} />
        )
      }
      statusText={statusParts.length ? statusParts.join(MEDIA_STATUS_SEPARATOR) : undefined}
      errorMessage={findSettledMediaError(scene.clipStatus, scene.clipError)}
      actionErrorMessage={generateClipMutation.error?.message}
    >
      <Button
        variant="secondary"
        disabled={isActionLocked}
        onClick={() => generateClipMutation.mutate({ sceneId: scene.id, action: "generate-clip" })}
      >
        {describeGenerateLabel(scene.clipStatus)}
      </Button>
      <FilmCancelRequestButton request={queuedRequest} isDisabled={isLocked} />
      {scene.clipStatus === "done" && trimDraft === undefined && (
        <Button variant="secondary" disabled={isLocked} onClick={() => setTrimDraft(sceneToTrimDraft(scene))}>
          Trim
        </Button>
      )}
      {trimDraft && (
        <ClipTrimForm
          sceneId={scene.id}
          trimDraft={trimDraft}
          isLocked={isLocked}
          onChange={setTrimDraft}
          onClose={() => setTrimDraft(undefined)}
        />
      )}
    </FilmScenePart>
  );
}

interface ClipTrimFormProps {
  sceneId: string;
  trimDraft: TrimDraft;
  isLocked: boolean;
  onChange: (trimDraft: TrimDraft) => void;
  onClose: () => void;
}

function ClipTrimForm({ sceneId, trimDraft, isLocked, onChange, onClose }: ClipTrimFormProps) {
  const trimMutation = useUpdateFilmSceneMutation();
  const trimStartMs = secondsTextToMs(trimDraft.startSecondsText);
  const trimEndMs = secondsTextToMs(trimDraft.endSecondsText);
  const isSaving = trimMutation.isPending;

  function handleSave() {
    if (trimStartMs === undefined || trimEndMs === undefined) return;
    trimMutation.mutate({ sceneId, changes: { trimStartMs, trimEndMs } }, { onSuccess: onClose });
  }

  return (
    <div className="flex w-full flex-col gap-3 rounded-lg border border-border p-3">
      <div className="grid grid-cols-2 gap-3">
        <TextField
          label="Start (s)"
          value={trimDraft.startSecondsText}
          inputMode="decimal"
          isDisabled={isLocked || isSaving}
          onChange={(startSecondsText) => onChange({ ...trimDraft, startSecondsText })}
        />
        <TextField
          label="End (s)"
          value={trimDraft.endSecondsText}
          inputMode="decimal"
          isDisabled={isLocked || isSaving}
          onChange={(endSecondsText) => onChange({ ...trimDraft, endSecondsText })}
        />
      </div>
      {trimMutation.isError && <ErrorAlert>{trimMutation.error.message}</ErrorAlert>}
      <div className="flex flex-wrap gap-2">
        <Button
          disabled={isLocked || isSaving || trimStartMs === undefined || trimEndMs === undefined}
          onClick={handleSave}
        >
          Save
        </Button>
        <Button variant="secondary" disabled={isSaving} onClick={onClose}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
