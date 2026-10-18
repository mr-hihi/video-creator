import type { Metadata } from "next";
import { FilmProjectDetailPanel } from "@/components/organisms/FilmProjectDetailPanel";
import { FilmStudioTemplate } from "@/components/templates/FilmStudioTemplate";

export const metadata: Metadata = {
  title: "Film project",
};

export default async function FilmProjectPage({ params }: PageProps<"/films/[id]">) {
  const { id } = await params;

  return (
    <FilmStudioTemplate>
      <FilmProjectDetailPanel projectId={id} />
    </FilmStudioTemplate>
  );
}
