import type { Metadata } from "next";
import { JobDetailTemplate } from "@/components/templates/JobDetailTemplate";
import { JobDetailPanel } from "@/components/organisms/JobDetailPanel";

export const metadata: Metadata = {
  title: "Job details",
};

export default async function JobDetailPage({ params }: PageProps<"/jobs/[id]">) {
  const { id } = await params;

  return (
    <JobDetailTemplate backHref="/" backLabel="All jobs">
      <JobDetailPanel jobId={id} />
    </JobDetailTemplate>
  );
}
