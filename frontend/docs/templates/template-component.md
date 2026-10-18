# Template — component

```tsx
// components/molecules/JobStatusBadge.tsx
import { Badge, type BadgeTone } from "@/components/atoms/Badge";
import type { JobStatus } from "@/features/jobs/types";

const JOB_STATUS_BADGES: Record<JobStatus, { label: string; tone: BadgeTone }> = {
  pending: { label: "Pending", tone: "neutral" },
  processing: { label: "Processing", tone: "info" },
  done: { label: "Done", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
};

interface JobStatusBadgeProps {
  status: JobStatus;
}

export function JobStatusBadge({ status }: JobStatusBadgeProps) {
  const { label, tone } = JOB_STATUS_BADGES[status];
  return <Badge tone={tone}>{label}</Badge>;
}
```

- Props interface named `<Component>Props`; lookup tables are constants outside the component.
- Token classes only (see [../styling.md](../styling.md)); no comments in JSX.
- Organisms add `"use client"` and call hooks from `features/*/queries.ts`.
