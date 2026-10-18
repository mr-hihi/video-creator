import type { Metadata } from "next";
import { FilmAnalysisDetailPanel } from "@/components/organisms/FilmAnalysisDetailPanel";
import { JobDetailTemplate } from "@/components/templates/JobDetailTemplate";

export const metadata: Metadata = {
  title: "Analysis details",
};

export default async function FilmAnalysisDetailPage({ params }: PageProps<"/film-analysis/[id]">) {
  const { id } = await params;

  return (
    <JobDetailTemplate backHref="/film-analysis" backLabel="All analyses">
      <FilmAnalysisDetailPanel jobId={id} />
    </JobDetailTemplate>
  );
}
