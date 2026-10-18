import type { Metadata } from "next";
import { FilmLibraryManager } from "@/components/organisms/FilmLibraryManager";
import { FilmStudioTemplate } from "@/components/templates/FilmStudioTemplate";

export const metadata: Metadata = {
  title: "Film library",
};

export default async function FilmLibraryPage({ searchParams }: PageProps<"/films/library">) {
  const { tab } = await searchParams;

  return (
    <FilmStudioTemplate>
      <FilmLibraryManager requestedTab={typeof tab === "string" ? tab : undefined} />
    </FilmStudioTemplate>
  );
}
