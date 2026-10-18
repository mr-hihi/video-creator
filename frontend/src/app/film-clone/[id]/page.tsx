import type { Metadata } from "next";
import { FilmCloneDetailPanel } from "@/components/organisms/FilmCloneDetailPanel";
import { JobDetailTemplate } from "@/components/templates/JobDetailTemplate";

export const metadata: Metadata = {
  title: "Clone details",
};

export default async function FilmCloneDetailPage({ params }: PageProps<"/film-clone/[id]">) {
  const { id } = await params;

  return (
    <JobDetailTemplate backHref="/film-clone" backLabel="All clones">
      <FilmCloneDetailPanel cloneId={id} />
    </JobDetailTemplate>
  );
}
