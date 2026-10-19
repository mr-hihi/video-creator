import { FilmEpisodePopup } from "@/components/organisms/FilmEpisodePopup";

export default async function FilmEpisodePopupPage({ params }: PageProps<"/films/[id]/episodes/[number]">) {
  const { id, number } = await params;

  return <FilmEpisodePopup projectId={id} episodeNumberText={number} />;
}
