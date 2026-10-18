import { useIsMutating, useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import type { UploadLanguage } from "@/features/jobs/constants";
import { apiFetch, apiUpload } from "@/lib/api/client";
import type {
  CloneAsset,
  CloneScene,
  FilmClone,
  FilmCloneDetail,
  GenerationRequest,
  LocalizationChoices,
  LocalizedAssetChanges,
  OriginalAssetChanges,
  SceneChanges,
} from "./types";
import { hasBusyFilmClone, isFilmCloneBusy } from "./utils";

const FILM_CLONES_PATH = "/film-clones";
const FILM_CLONE_LIST_LIMIT = 50;
const FILM_CLONE_POLL_INTERVAL_MS = 3_000;
const YOUTUBE_CLONE_REQUEST_TIMEOUT_MS = 45_000;
const CAPTCHA_TOKEN_HEADER = "X-Captcha-Token";

export interface CreateFilmCloneRequest {
  file: File;
  language: UploadLanguage;
  presetId?: string;
  maxFrames: number;
  automaticChoices?: LocalizationChoices;
  captchaToken?: string;
  onUploadProgress: (uploadedPercent: number) => void;
}

export interface CreateYoutubeFilmCloneRequest {
  url: string;
  language: UploadLanguage;
  presetId?: string;
  maxFrames: number;
  automaticChoices?: LocalizationChoices;
  captchaToken?: string;
}

export interface LocalizeFilmCloneRequest {
  cloneId: string;
  choices: LocalizationChoices;
}

export interface UpdateCloneAssetRequest {
  assetId: string;
  changes: OriginalAssetChanges | LocalizedAssetChanges;
}

export interface UpdateCloneSceneRequest {
  sceneId: string;
  changes: SceneChanges;
}

export const filmCloneQueryKeys = {
  all: ["filmClones"] as const,
  lists: () => [...filmCloneQueryKeys.all, "list"] as const,
  list: (limit: number) => [...filmCloneQueryKeys.lists(), limit] as const,
  details: () => [...filmCloneQueryKeys.all, "detail"] as const,
  detail: (cloneId: string) => [...filmCloneQueryKeys.details(), cloneId] as const,
};

const filmCloneMutationKeys = {
  creations: () => [...filmCloneQueryKeys.all, "create"] as const,
};

export function useFilmClonesQuery() {
  return useQuery({
    queryKey: filmCloneQueryKeys.list(FILM_CLONE_LIST_LIMIT),
    queryFn: ({ signal }) => fetchFilmClones(FILM_CLONE_LIST_LIMIT, signal),
    refetchInterval: (query) => (hasBusyFilmClone(query.state.data ?? []) ? FILM_CLONE_POLL_INTERVAL_MS : false),
  });
}

export function useFilmCloneQuery(cloneId: string) {
  return useQuery({
    queryKey: filmCloneQueryKeys.detail(cloneId),
    queryFn: ({ signal }) => apiFetch<FilmCloneDetail>(buildFilmClonePath(cloneId), { signal }),
    refetchInterval: (query) => {
      const clone = query.state.data;
      return clone && isFilmCloneBusy(clone) ? FILM_CLONE_POLL_INTERVAL_MS : false;
    },
  });
}

export function useCreateFilmCloneMutation() {
  return useFilmCloneCreationMutation(createFilmClone);
}

export function useCreateYoutubeFilmCloneMutation() {
  return useFilmCloneCreationMutation(createYoutubeFilmClone);
}

export function useIsCreatingFilmClone(): boolean {
  return useIsMutating({ mutationKey: filmCloneMutationKeys.creations() }) > 0;
}

export function useDeleteFilmCloneMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (cloneId: string) => apiFetch<void>(buildFilmClonePath(cloneId), { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filmCloneQueryKeys.lists() }),
  });
}

export function useLocalizeFilmCloneMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ cloneId, choices }: LocalizeFilmCloneRequest) =>
      apiFetch<FilmClone>(`${buildFilmClonePath(cloneId)}/localization`, {
        method: "POST",
        body: JSON.stringify(choices),
      }),
    onSuccess: (clone) => invalidateFilmClone(queryClient, clone.id),
  });
}

export function useWriteCloneScriptMutation() {
  return useFilmCloneActionMutation("write-script");
}

export function useResumeFilmCloneMutation() {
  return useFilmCloneActionMutation("resume");
}

export function useRelocalizeFilmCloneMutation() {
  return useFilmCloneActionMutation("relocalize");
}

export function useUpdateCloneAssetMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ assetId, changes }: UpdateCloneAssetRequest) =>
      apiFetch<CloneAsset>(buildCloneAssetPath(assetId), { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: () => invalidateFilmCloneDetails(queryClient),
  });
}

export function useDeleteCloneAssetMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assetId: string) => apiFetch<void>(buildCloneAssetPath(assetId), { method: "DELETE" }),
    onSuccess: () => invalidateFilmCloneDetails(queryClient),
  });
}

export function useGenerateAssetReferenceMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (assetId: string) =>
      apiFetch<GenerationRequest>(`${buildCloneAssetPath(assetId)}/generate-reference`, { method: "POST" }),
    onSuccess: () => invalidateFilmCloneDetails(queryClient),
  });
}

export function useUpdateCloneSceneMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sceneId, changes }: UpdateCloneSceneRequest) =>
      apiFetch<CloneScene>(buildCloneScenePath(sceneId), { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: () => invalidateFilmCloneDetails(queryClient),
  });
}

export function useGenerateSceneImageMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sceneId: string) =>
      apiFetch<GenerationRequest>(`${buildCloneScenePath(sceneId)}/generate-image`, { method: "POST" }),
    onSuccess: () => invalidateFilmCloneDetails(queryClient),
  });
}

function useFilmCloneCreationMutation<TRequest>(mutationFn: (request: TRequest) => Promise<FilmClone>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: filmCloneMutationKeys.creations(),
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filmCloneQueryKeys.lists() }),
  });
}

function useFilmCloneActionMutation(actionPath: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (cloneId: string) =>
      apiFetch<FilmClone>(`${buildFilmClonePath(cloneId)}/${actionPath}`, { method: "POST" }),
    onSuccess: (clone) => invalidateFilmClone(queryClient, clone.id),
  });
}

function invalidateFilmClone(queryClient: QueryClient, cloneId: string): Promise<void[]> {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: filmCloneQueryKeys.lists() }),
    queryClient.invalidateQueries({ queryKey: filmCloneQueryKeys.detail(cloneId) }),
  ]);
}

function invalidateFilmCloneDetails(queryClient: QueryClient): Promise<void> {
  return queryClient.invalidateQueries({ queryKey: filmCloneQueryKeys.details() });
}

function fetchFilmClones(limit: number, signal: AbortSignal): Promise<FilmClone[]> {
  const searchParams = new URLSearchParams({ limit: String(limit) });
  return apiFetch<FilmClone[]>(`${FILM_CLONES_PATH}?${searchParams.toString()}`, { signal });
}

function createFilmClone(request: CreateFilmCloneRequest): Promise<FilmClone> {
  const formData = new FormData();
  formData.append("file", request.file);
  formData.append("language", request.language);
  formData.append("maxFrames", String(request.maxFrames));
  if (request.presetId) formData.append("presetId", request.presetId);
  if (request.automaticChoices) appendAutomaticChoices(formData, request.automaticChoices);
  return apiUpload<FilmClone>(FILM_CLONES_PATH, {
    body: formData,
    headers: buildCaptchaHeaders(request.captchaToken),
    onUploadProgress: request.onUploadProgress,
  });
}

function createYoutubeFilmClone(request: CreateYoutubeFilmCloneRequest): Promise<FilmClone> {
  return apiFetch<FilmClone>(`${FILM_CLONES_PATH}/youtube`, {
    method: "POST",
    body: JSON.stringify({
      url: request.url,
      language: request.language,
      presetId: request.presetId,
      maxFrames: request.maxFrames,
      ...(request.automaticChoices && { shouldRunAutomatically: true, ...request.automaticChoices }),
    }),
    headers: buildCaptchaHeaders(request.captchaToken),
    timeoutMs: YOUTUBE_CLONE_REQUEST_TIMEOUT_MS,
  });
}

function appendAutomaticChoices(formData: FormData, choices: LocalizationChoices): void {
  formData.append("shouldRunAutomatically", "true");
  if (choices.targetCountry) formData.append("targetCountry", choices.targetCountry);
  if (choices.targetSetting) formData.append("targetSetting", choices.targetSetting);
  formData.append("changeAppearance", String(choices.changeAppearance));
  formData.append("changeCostume", String(choices.changeCostume));
  formData.append("changeSetting", String(choices.changeSetting));
}

function buildFilmClonePath(cloneId: string): string {
  return `${FILM_CLONES_PATH}/${encodeURIComponent(cloneId)}`;
}

function buildCloneAssetPath(assetId: string): string {
  return `${FILM_CLONES_PATH}/assets/${encodeURIComponent(assetId)}`;
}

function buildCloneScenePath(sceneId: string): string {
  return `${FILM_CLONES_PATH}/scenes/${encodeURIComponent(sceneId)}`;
}

function buildCaptchaHeaders(captchaToken: string | undefined): Record<string, string> {
  return captchaToken ? { [CAPTCHA_TOKEN_HEADER]: captchaToken } : {};
}
