import type { Metadata } from "next";
import { FilmCloneHistory } from "@/components/organisms/FilmCloneHistory";
import { NewFilmCloneForm } from "@/components/organisms/NewFilmCloneForm";
import { FilmCloneTemplate } from "@/components/templates/FilmCloneTemplate";

export const metadata: Metadata = {
  title: "Film Clone",
};

export default function FilmClonePage() {
  return <FilmCloneTemplate cloneForm={<NewFilmCloneForm />} cloneHistory={<FilmCloneHistory />} />;
}
