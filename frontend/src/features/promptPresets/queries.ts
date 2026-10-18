import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, apiUpload } from "@/lib/api/client";
import type {
  PresetPrompts,
  PromptDefaults,
  PromptPreset,
  PromptPresetDetail,
  PromptPresetVersion,
  PromptPresetVersionDetail,
} from "./types";

const PROMPT_PRESETS_PATH = "/prompt-presets";

export interface SavePromptPresetRequest {
  presetId: string;
  name: string;
  prompts: PresetPrompts;
}

export interface RestorePromptPresetVersionRequest {
  presetId: string;
  version: number;
}

export const promptPresetQueryKeys = {
  all: ["promptPresets"] as const,
  lists: () => [...promptPresetQueryKeys.all, "list"] as const,
  defaults: () => [...promptPresetQueryKeys.all, "defaults"] as const,
  detail: (presetId: string) => [...promptPresetQueryKeys.all, "detail", presetId] as const,
  versions: (presetId: string) => [...promptPresetQueryKeys.all, "versions", presetId] as const,
  version: (presetId: string, version: number) =>
    [...promptPresetQueryKeys.all, "version", presetId, version] as const,
};

export function usePromptPresetsQuery() {
  return useQuery({
    queryKey: promptPresetQueryKeys.lists(),
    queryFn: ({ signal }) => apiFetch<PromptPreset[]>(PROMPT_PRESETS_PATH, { signal }),
  });
}

export function usePromptDefaultsQuery() {
  return useQuery({
    queryKey: promptPresetQueryKeys.defaults(),
    queryFn: ({ signal }) => apiFetch<PromptDefaults>(`${PROMPT_PRESETS_PATH}/defaults`, { signal }),
    staleTime: Infinity,
  });
}

export function usePromptPresetQuery(presetId: string) {
  return useQuery({
    queryKey: promptPresetQueryKeys.detail(presetId),
    queryFn: ({ signal }) => apiFetch<PromptPresetDetail>(buildPresetPath(presetId), { signal }),
  });
}

export function usePromptPresetVersionsQuery(presetId: string) {
  return useQuery({
    queryKey: promptPresetQueryKeys.versions(presetId),
    queryFn: ({ signal }) => apiFetch<PromptPresetVersion[]>(`${buildPresetPath(presetId)}/versions`, { signal }),
  });
}

export function usePromptPresetVersionQuery(presetId: string, version: number) {
  return useQuery({
    queryKey: promptPresetQueryKeys.version(presetId, version),
    queryFn: ({ signal }) =>
      apiFetch<PromptPresetVersionDetail>(`${buildPresetPath(presetId)}/versions/${version}`, { signal }),
  });
}

export function useCreatePromptPresetMutation() {
  return usePresetMutation((name: string) =>
    apiFetch<PromptPresetDetail>(PROMPT_PRESETS_PATH, { method: "POST", body: JSON.stringify({ name }) }),
  );
}

export function useSavePromptPresetMutation(onSaved: (savedPreset: PromptPresetDetail) => void) {
  return usePresetMutation(
    (request: SavePromptPresetRequest) =>
      apiFetch<PromptPresetDetail>(buildPresetPath(request.presetId), {
        method: "PUT",
        body: JSON.stringify({ name: request.name, prompts: request.prompts }),
      }),
    onSaved,
  );
}

export function useDeletePromptPresetMutation(onDeleted: () => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (presetId: string) => apiFetch<void>(buildPresetPath(presetId), { method: "DELETE" }),
    onSuccess: async (_response, presetId) => {
      await queryClient.invalidateQueries({
        queryKey: promptPresetQueryKeys.all,
        predicate: (query) => !query.queryKey.includes(presetId),
      });
      onDeleted();
    },
  });
}

export function useMarkDefaultPromptPresetMutation() {
  return usePresetMutation((presetId: string) =>
    apiFetch<PromptPreset>(`${buildPresetPath(presetId)}/default`, { method: "POST" }),
  );
}

export function useDuplicatePromptPresetMutation() {
  return usePresetMutation((presetId: string) =>
    apiFetch<PromptPresetDetail>(`${buildPresetPath(presetId)}/duplicate`, { method: "POST" }),
  );
}

export function useRestorePromptPresetVersionMutation(onRestored: (restoredPreset: PromptPresetDetail) => void) {
  return usePresetMutation(
    (request: RestorePromptPresetVersionRequest) =>
      apiFetch<PromptPresetDetail>(`${buildPresetPath(request.presetId)}/versions/${request.version}/restore`, {
        method: "POST",
      }),
    onRestored,
  );
}

export function useImportPromptPresetMutation() {
  return usePresetMutation((file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiUpload<PromptPresetDetail>(`${PROMPT_PRESETS_PATH}/import`, { body: formData });
  });
}

function usePresetMutation<TRequest, TResponse>(
  mutationFn: (request: TRequest) => Promise<TResponse>,
  onRefreshed?: (response: TResponse) => void,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: promptPresetQueryKeys.all });
      // Not in mutate() options: the editor remounts on a new version, and TanStack drops those for an unmounted caller.
      onRefreshed?.(response);
    },
  });
}

function buildPresetPath(presetId: string): string {
  return `${PROMPT_PRESETS_PATH}/${encodeURIComponent(presetId)}`;
}
