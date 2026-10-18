# Template — query / mutation hook

```ts
// features/jobs/queries.ts
export const jobQueryKeys = {
  all: ["jobs"] as const,
  lists: () => [...jobQueryKeys.all, "list"] as const,
  list: (limit: number) => [...jobQueryKeys.lists(), limit] as const,
  detail: (jobId: string) => [...jobQueryKeys.all, "detail", jobId] as const,
};

export function useJobQuery(jobId: string) {
  return useQuery({
    queryKey: jobQueryKeys.detail(jobId),
    queryFn: ({ signal }) => fetchJob(jobId, signal),
    refetchInterval: (query) => {
      const job = query.state.data;
      return job && isJobInProgress(job) ? JOB_POLL_INTERVAL_MS : false;
    },
  });
}

function fetchJob(jobId: string, signal: AbortSignal): Promise<JobDetail> {
  return apiFetch<JobDetail>(`/jobs/${encodeURIComponent(jobId)}`, { signal });
}
```

- Pass the query's `signal` into `apiFetch` so unmounts cancel the request.
- Keep `fetchX` private to `queries.ts`; components import only the hook.
