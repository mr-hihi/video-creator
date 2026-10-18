"use client";

import Link from "next/link";
import { DELETED_SOURCE_LABEL } from "@/features/jobs/constants";
import { useJobQuery } from "@/features/jobs/queries";
import { buildFilmAnalysisDetailPath } from "@/features/jobs/utils";
import { isNotFoundError } from "@/lib/api/client";

interface RerunSourceLinkProps {
  sourceJobId: string;
}

export function RerunSourceLink({ sourceJobId }: RerunSourceLinkProps) {
  const sourceJobQuery = useJobQuery(sourceJobId);

  if (isNotFoundError(sourceJobQuery.error)) return <span>{DELETED_SOURCE_LABEL}</span>;
  return (
    <Link href={buildFilmAnalysisDetailPath(sourceJobId)} className="text-accent hover:underline">
      {sourceJobQuery.data?.sourceFilename ?? sourceJobId}
    </Link>
  );
}
