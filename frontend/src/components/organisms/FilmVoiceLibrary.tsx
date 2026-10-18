"use client";

import { useState } from "react";
import { AudioPlayer } from "@/components/atoms/AudioPlayer";
import { Badge } from "@/components/atoms/Badge";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { Panel } from "@/components/atoms/Panel";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { CONSENT_BADGE_LABEL, EMPTY_VALUE_LABEL } from "@/features/films/constants";
import { useFilmVoicesQuery } from "@/features/films/queries";
import { buildFilmFileUrl, describeDuration } from "@/features/films/utils";
import { FilmVoiceForm } from "./FilmVoiceForm";

type OpenVoiceForm = { kind: "new" } | { kind: "edit"; voiceId: string };

export function FilmVoiceLibrary() {
  const voicesQuery = useFilmVoicesQuery();
  const [openForm, setOpenForm] = useState<OpenVoiceForm>();

  const voices = voicesQuery.data ?? [];
  const openedVoice = openForm?.kind === "edit" ? voices.find((voice) => voice.id === openForm.voiceId) : undefined;
  const isFormOpen = openForm?.kind === "new" || openedVoice !== undefined;

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <Panel
        title="Voices"
        headerAction={
          <Button disabled={openForm?.kind === "new"} onClick={() => setOpenForm({ kind: "new" })}>
            New voice
          </Button>
        }
      >
        {voicesQuery.isPending && <PlaceholderMessage>Loading voices…</PlaceholderMessage>}
        {voicesQuery.isError && <ErrorAlert>{voicesQuery.error.message}</ErrorAlert>}
        {voicesQuery.isSuccess && !voices.length && <PlaceholderMessage>{EMPTY_VALUE_LABEL}</PlaceholderMessage>}
        <ul className="divide-y divide-border">
          {voices.map((voice) => (
            <li key={voice.id} className="flex flex-col gap-2 py-3">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <button
                  type="button"
                  onClick={() => setOpenForm({ kind: "edit", voiceId: voice.id })}
                  className="min-w-0 text-left text-sm font-medium break-all hover:text-accent hover:underline focus-visible:outline-2 focus-visible:outline-accent"
                >
                  {voice.name}
                </button>
                <span className="text-xs text-muted tabular-nums">{describeDuration(voice.sampleDurationMs)}</span>
                {voice.consentPath && <Badge tone="success">{CONSENT_BADGE_LABEL}</Badge>}
              </div>
              {voice.description && <p className="text-xs text-muted">{voice.description}</p>}
              <AudioPlayer src={buildFilmFileUrl(voice.samplePath, voice.updatedAt)} label={`${voice.name} sample`} />
              <p className="text-sm break-words">{voice.sampleText}</p>
            </li>
          ))}
        </ul>
      </Panel>
      {isFormOpen && (
        <Panel title={openedVoice ? openedVoice.name : "New voice"}>
          <FilmVoiceForm key={openedVoice?.id ?? "new"} voice={openedVoice} onClose={() => setOpenForm(undefined)} />
        </Panel>
      )}
    </div>
  );
}
