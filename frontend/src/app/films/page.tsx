import type { Metadata } from "next";
import { FilmProjectsOverview } from "@/components/organisms/FilmProjectsOverview";
import { FilmStudioTemplate } from "@/components/templates/FilmStudioTemplate";

export const metadata: Metadata = {
  title: "Film Studio",
};

export default function FilmStudioPage() {
  return (
    <FilmStudioTemplate>
      <FilmProjectsOverview />
    </FilmStudioTemplate>
  );
}
