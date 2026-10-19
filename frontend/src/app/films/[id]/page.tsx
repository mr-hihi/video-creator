import type { Metadata } from "next";
import { FilmProjectDetailPanel } from "@/components/organisms/FilmProjectDetailPanel";
import { FilmStudioTemplate } from "@/components/templates/FilmStudioTemplate";

export const metadata: Metadata = {
  title: "Film project",
};

export default async function FilmProjectPage({ params, searchParams }: PageProps<"/films/[id]">) {
  const { id } = await params;
  const { tab } = await searchParams;

  return (
    <FilmStudioTemplate>
      <FilmProjectDetailPanel projectId={id} requestedTab={typeof tab === "string" ? tab : undefined} />
    </FilmStudioTemplate>
  );
}
