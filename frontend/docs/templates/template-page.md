# Template — page

```tsx
// src/app/jobs/[id]/page.tsx
import type { Metadata } from "next";
import { JobDetailTemplate } from "@/components/templates/JobDetailTemplate";
import { JobDetailPanel } from "@/components/organisms/JobDetailPanel";

export const metadata: Metadata = {
  title: "Job details",
};

export default async function JobDetailPage({ params }: PageProps<"/jobs/[id]">) {
  const { id } = await params;

  return (
    <JobDetailTemplate>
      <JobDetailPanel jobId={id} />
    </JobDetailTemplate>
  );
}
```

- The page only picks a template and fills its slots; data loading lives in the client organism.
- Loading / error / empty states are handled inside the organism (`PlaceholderMessage`, `ErrorAlert`).
