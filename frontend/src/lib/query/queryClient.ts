import { QueryClient, isServer } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/client";

const MAX_QUERY_RETRY_COUNT = 2;

let browserQueryClient: QueryClient | undefined;

export function getQueryClient(): QueryClient {
  if (isServer) return createQueryClient();
  browserQueryClient ??= createQueryClient();
  return browserQueryClient;
}

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: shouldRetryQuery },
    },
  });
}

function shouldRetryQuery(failureCount: number, error: Error): boolean {
  if (error instanceof ApiError && error.isClientError) return false;
  return failureCount < MAX_QUERY_RETRY_COUNT;
}
