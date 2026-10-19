"use client";

import { AudioPlayer } from "@/components/atoms/AudioPlayer";
import { Button } from "@/components/atoms/Button";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { FilmScenePart } from "@/components/molecules/FilmScenePart";
import type { GenerationRequest } from "@/features/filmClones/types";
import { useGenerateSceneMediaMutation } from "@/features/films/queries";
import type { Scene } from "@/features/films/types";
import {
  buildFilmFileUrl,
  describeBusyMedia,
  describeGenerateLabel,
  findQueuedRequest,
  findSettledMediaError,
} from "@/features/films/utils";
import { MISSING_OUTPUT_MESSAGE } from "@/features/jobs/constants";
import { FilmCancelRequestButton } from "./FilmCancelRequestButton";

interface FilmSceneNarrationPartProps {
  scene: Scene;
  sceneNumber: number;
  openRequests: readonly GenerationRequest[];
  isLocked: boolean;
  isSceneBusy: boolean;
}

export function FilmSceneNarrationPart({
  scene,
  sceneNumber,
  openRequests,
  isLocked,
  isSceneBusy,
}: FilmSceneNarrationPartProps) {
  const generateNarrationMutation = useGenerateSceneMediaMutation();
  const busyLabel = describeBusyMedia(scene.narrationStatus);
  const queuedRequest = findQueuedRequest(
    openRequests,
    (request) => request.sceneId === scene.id && request.kind === "narration",
  );

  return (
    <FilmScenePart
      title="Narration"
      media={
        scene.narrationPath ? (
          <AudioPlayer
            src={buildFilmFileUrl(scene.narrationPath, scene.updatedAt)}
            label={`Scene ${sceneNumber} narration`}
          />
        ) : (
          <PlaceholderMessage>{busyLabel ?? MISSING_OUTPUT_MESSAGE}</PlaceholderMessage>
        )
      }
      statusText={busyLabel}
      errorMessage={findSettledMediaError(scene.narrationStatus, scene.narrationError)}
      actionErrorMessage={generateNarrationMutation.error?.message}
    >
      <Button
        variant="secondary"
        disabled={isLocked || isSceneBusy || generateNarrationMutation.isPending}
        onClick={() => generateNarrationMutation.mutate({ sceneId: scene.id, action: "generate-narration" })}
      >
        {describeGenerateLabel(scene.narrationStatus)}
      </Button>
      <FilmCancelRequestButton request={queuedRequest} isDisabled={isLocked} />
    </FilmScenePart>
  );
}
