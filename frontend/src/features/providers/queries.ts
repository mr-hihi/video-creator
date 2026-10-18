import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { ConnectionTest, Provider, ProviderId, ProviderSettings, ProviderUpdate } from "./types";
import { listAnalysisProviders } from "./utils";

const PROVIDER_SETTINGS_PATH = "/settings/providers";
const GOOGLE_FLOW_SETTINGS_PATH = `${PROVIDER_SETTINGS_PATH}/google_flow`;
const CONNECTION_TEST_REQUEST_TIMEOUT_MS = 30_000;

export interface UpdateProviderRequest {
  providerId: ProviderId;
  update: ProviderUpdate;
}

export const providerQueryKeys = {
  all: ["providers"] as const,
  settings: () => [...providerQueryKeys.all, "settings"] as const,
};

const providerSettingsQueryOptions = queryOptions({
  queryKey: providerQueryKeys.settings(),
  queryFn: ({ signal }) => apiFetch<ProviderSettings>(PROVIDER_SETTINGS_PATH, { signal }),
});

export function useProviderSettingsQuery(refetchIntervalMs?: number) {
  return useQuery({ ...providerSettingsQueryOptions, refetchInterval: refetchIntervalMs });
}

export function useAnalysisProvidersQuery() {
  return useQuery({ ...providerSettingsQueryOptions, select: listAnalysisProviders });
}

export function useUpdateProviderMutation(onSaved: () => void) {
  return useProviderMutation(
    (request: UpdateProviderRequest) =>
      apiFetch<Provider>(buildProviderPath(request.providerId), {
        method: "PATCH",
        body: JSON.stringify(request.update),
      }),
    onSaved,
  );
}

export function useTestProviderConnectionMutation() {
  return useProviderMutation((providerId: ProviderId) =>
    apiFetch<ConnectionTest>(`${buildProviderPath(providerId)}/test`, {
      method: "POST",
      timeoutMs: CONNECTION_TEST_REQUEST_TIMEOUT_MS,
    }),
  );
}

export function useResumeGoogleFlowMutation() {
  return useProviderMutation<void, Provider>(() =>
    apiFetch<Provider>(`${GOOGLE_FLOW_SETTINGS_PATH}/resume`, { method: "POST" }),
  );
}

export function useOpenFlowTabMutation() {
  return useMutation({
    mutationFn: () => apiFetch<void>(`${GOOGLE_FLOW_SETTINGS_PATH}/open-tab`, { method: "POST" }),
  });
}

function useProviderMutation<TRequest, TResponse>(
  mutationFn: (request: TRequest) => Promise<TResponse>,
  onRefreshed?: () => void,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: providerQueryKeys.all });
      onRefreshed?.();
    },
  });
}

function buildProviderPath(providerId: ProviderId): string {
  return `${PROVIDER_SETTINGS_PATH}/${encodeURIComponent(providerId)}`;
}
