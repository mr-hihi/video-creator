import type { Metadata } from "next";
import { FilmEpisodePanel } from "@/components/organisms/FilmEpisodePanel";
import { FilmStudioTemplate } from "@/components/templates/FilmStudioTemplate";

export const metadata: Metadata = {
  title: "Film episode",
};

export default async function FilmEpisodePage({ params }: PageProps<"/films/[id]/episodes/[number]">) {
  const { id, number } = await params;

  return (
    <FilmStudioTemplate>
      <FilmEpisodePanel projectId={id} episodeNumberText={number} />
    </FilmStudioTemplate>
  );
}
