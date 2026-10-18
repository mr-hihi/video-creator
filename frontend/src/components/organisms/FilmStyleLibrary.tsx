"use client";

import { useState } from "react";
import { Badge } from "@/components/atoms/Badge";
import { Button } from "@/components/atoms/Button";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import { Panel } from "@/components/atoms/Panel";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { BUILT_IN_BADGE_LABEL } from "@/features/films/constants";
import { useFilmStylesQuery } from "@/features/films/queries";
import { FilmStyleForm } from "./FilmStyleForm";

type OpenStyleForm = { kind: "new" } | { kind: "edit"; styleId: string };

export function FilmStyleLibrary() {
  const stylesQuery = useFilmStylesQuery();
  const [openForm, setOpenForm] = useState<OpenStyleForm>();

  const styles = stylesQuery.data ?? [];
  const openedStyle = openForm?.kind === "edit" ? styles.find((style) => style.id === openForm.styleId) : undefined;
  const isFormOpen = openForm?.kind === "new" || openedStyle !== undefined;

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <Panel
        title="Styles"
        headerAction={
          <Button disabled={openForm?.kind === "new"} onClick={() => setOpenForm({ kind: "new" })}>
            New style
          </Button>
        }
      >
        {stylesQuery.isPending && <PlaceholderMessage>Loading styles…</PlaceholderMessage>}
        {stylesQuery.isError && <ErrorAlert>{stylesQuery.error.message}</ErrorAlert>}
        <ul className="divide-y divide-border">
          {styles.map((style) => (
            <li key={style.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5">
              <button
                type="button"
                onClick={() => setOpenForm({ kind: "edit", styleId: style.id })}
                className="min-w-0 text-left text-sm font-medium break-words hover:text-accent hover:underline focus-visible:outline-2 focus-visible:outline-accent"
              >
                {style.name}
              </button>
              {style.isBuiltin && <Badge tone="neutral">{BUILT_IN_BADGE_LABEL}</Badge>}
            </li>
          ))}
        </ul>
      </Panel>
      {isFormOpen && (
        <Panel title={openedStyle ? openedStyle.name : "New style"}>
          <FilmStyleForm key={openedStyle?.id ?? "new"} style={openedStyle} onClose={() => setOpenForm(undefined)} />
        </Panel>
      )}
    </div>
  );
}
