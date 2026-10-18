import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { providerQueryKeys, useAnalysisProvidersQuery, useProviderSettingsQuery } from "@/features/providers/queries";
import { apiFetch } from "@/lib/api/client";
import type {
  AiModelStatus,
  AiModelsSaveResult,
  AiModelsUpdate,
  AiStepGroup,
  AppSettings,
  MediaProviderStatus,
} from "./types";
import { buildAiModelStatus, buildMediaProviderStatus } from "./utils";

const APP_SETTINGS_PATH = "/settings";
const AI_MODELS_SETTINGS_PATH = `${APP_SETTINGS_PATH}/ai-models`;

export const appSettingQueryKeys = {
  all: ["appSettings"] as const,
};

export function useAppSettingsQuery() {
  return useQuery({
    queryKey: appSettingQueryKeys.all,
    queryFn: ({ signal }) => apiFetch<AppSettings>(APP_SETTINGS_PATH, { signal }),
  });
}

export function useAiModelStatus(groups: readonly AiStepGroup[]): AiModelStatus | undefined {
  const { data: settings } = useAppSettingsQuery();
  const { data: analysisProviders } = useAnalysisProvidersQuery();
  if (!settings || !analysisProviders) return undefined;
  return buildAiModelStatus(settings, analysisProviders, groups);
}

export function useMediaProviderStatus(): MediaProviderStatus | undefined {
  const { data: settings } = useAppSettingsQuery();
  const { data: providerSettings } = useProviderSettingsQuery();
  if (!settings || !providerSettings) return undefined;
  return buildMediaProviderStatus(settings, providerSettings);
}

export function useUpdateAppSettingsMutation(onSaved: (savedSettings: AppSettings) => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (changedSettings: Partial<AppSettings>) =>
      apiFetch<AppSettings>(APP_SETTINGS_PATH, { method: "PATCH", body: JSON.stringify(changedSettings) }),
    onSuccess: async (savedSettings) => {
      await queryClient.invalidateQueries({ queryKey: appSettingQueryKeys.all });
      onSaved(savedSettings);
    },
  });
}

export function useUpdateAiModelsMutation(onSaved: () => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (update: AiModelsUpdate) =>
      apiFetch<AiModelsSaveResult>(AI_MODELS_SETTINGS_PATH, { method: "PATCH", body: JSON.stringify(update) }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: appSettingQueryKeys.all }),
        queryClient.invalidateQueries({ queryKey: providerQueryKeys.all }),
      ]);
      onSaved();
    },
  });
}
