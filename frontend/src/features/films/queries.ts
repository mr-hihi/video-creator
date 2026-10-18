import { useMutation, useMutationState, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import type { GenerationRequest } from "@/features/filmClones/types";
import { apiFetch, apiUpload } from "@/lib/api/client";
import { FILM_STUDIO_REFRESH_INTERVAL_MS } from "./constants";
import type {
  CharacterFields,
  CreateEpisodeFields,
  CreateProjectFields,
  Episode,
  EpisodeAction,
  EpisodeChanges,
  EpisodeDetail,
  FilmCharacter,
  FilmCharacterDetail,
  FilmProject,
  FilmProjectDetail,
  FilmStyle,
  ProjectChanges,
  ProjectStatus,
  Scene,
  SceneChanges,
  SceneGenerationAction,
  ScenePromptFields,
  StyleFields,
  VoiceChanges,
  VoiceTemplate,
} from "./types";
import { isFilmEpisodeBusy, isFilmProjectBusy } from "./utils";

const FILMS_API_PATH = "/films";
const CAPTCHA_TOKEN_HEADER = "X-Captcha-Token";

export interface UpdateProjectRequest {
  projectId: string;
  changes: ProjectChanges;
}

export interface ProjectCharacterRequest {
  projectId: string;
  characterId: string;
}

export interface EditCharacterReferenceRequest extends ProjectCharacterRequest {
  prompt: string;
}

export interface UpdateCharacterRequest {
  characterId: string;
  changes: Partial<CharacterFields>;
}

export interface UploadCharacterReferenceRequest {
  characterId: string;
  file: File;
}

export interface UpdateStyleRequest {
  styleId: string;
  changes: Partial<StyleFields>;
}

export interface CreateVoiceRequest {
  file: File;
  name: string;
  sampleText: string;
  description: string;
}

export interface UpdateVoiceRequest {
  voiceId: string;
  changes: VoiceChanges;
}

export interface UploadVoiceConsentRequest {
  voiceId: string;
  file: File;
}

export interface CreateEpisodeRequest {
  projectId: string;
  fields: CreateEpisodeFields;
  captchaToken?: string;
}

export interface UpdateEpisodeRequest {
  episodeId: string;
  changes: EpisodeChanges;
}

export interface EpisodeActionRequest {
  episodeId: string;
  action: EpisodeAction;
}

export interface ChooseThumbnailRequest {
  episodeId: string;
  candidate: number;
}

export interface CreateSceneRequest {
  episodeId: string;
  afterPosition?: number;
  fields: ScenePromptFields;
}

export interface UpdateSceneRequest {
  sceneId: string;
  changes: SceneChanges;
}

export interface UploadSceneImageRequest {
  sceneId: string;
  file: File;
}

export interface GenerateSceneMediaRequest {
  sceneId: string;
  action: SceneGenerationAction;
}

export interface EditSceneImageRequest {
  sceneId: string;
  prompt: string;
}

export const filmQueryKeys = {
  all: ["films"] as const,
  projects: () => [...filmQueryKeys.all, "projects"] as const,
  projectLists: () => [...filmQueryKeys.projects(), "list"] as const,
  projectList: (status: ProjectStatus) => [...filmQueryKeys.projectLists(), status] as const,
  projectDetail: (projectId: string) => [...filmQueryKeys.projects(), "detail", projectId] as const,
  characters: () => [...filmQueryKeys.all, "characters"] as const,
  characterList: () => [...filmQueryKeys.characters(), "list"] as const,
  characterDetail: (characterId: string) => [...filmQueryKeys.characters(), "detail", characterId] as const,
  styles: () => [...filmQueryKeys.all, "styles"] as const,
  voices: () => [...filmQueryKeys.all, "voices"] as const,
  episodes: () => [...filmQueryKeys.all, "episodes"] as const,
  episodeDetail: (episodeId: string) => [...filmQueryKeys.episodes(), "detail", episodeId] as const,
};

const filmMutationKeys = {
  episodeActions: () => [...filmQueryKeys.all, "episodeAction"] as const,
};

export function useFilmProjectsQuery(status: ProjectStatus) {
  return useQuery({
    queryKey: filmQueryKeys.projectList(status),
    queryFn: ({ signal }) => fetchFilmProjects(status, signal),
  });
}

export function useFilmProjectQuery(projectId: string) {
  return useQuery({
    queryKey: filmQueryKeys.projectDetail(projectId),
    queryFn: ({ signal }) => apiFetch<FilmProjectDetail>(buildProjectPath(projectId), { signal }),
    refetchInterval: (query) => {
      const project = query.state.data;
      return project && isFilmProjectBusy(project) ? FILM_STUDIO_REFRESH_INTERVAL_MS : false;
    },
  });
}

export function useCreateFilmProjectMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (fields: CreateProjectFields) =>
      apiFetch<FilmProjectDetail>(`${FILMS_API_PATH}/projects`, { method: "POST", body: JSON.stringify(fields) }),
    onSuccess: () => invalidateProjectsAndCharacters(queryClient),
  });
}

export function useUpdateFilmProjectMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, changes }: UpdateProjectRequest) =>
      apiFetch<FilmProjectDetail>(buildProjectPath(projectId), { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filmQueryKeys.projects() }),
  });
}

export function useArchiveFilmProjectMutation() {
  return useProjectStatusMutation("archive");
}

export function useUnarchiveFilmProjectMutation() {
  return useProjectStatusMutation("unarchive");
}

export function useDeleteFilmProjectMutation(onDeleted: () => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (projectId: string) => apiFetch<void>(buildProjectPath(projectId), { method: "DELETE" }),
    onSuccess: () => {
      onDeleted();
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: filmQueryKeys.projectLists() }),
        queryClient.invalidateQueries({ queryKey: filmQueryKeys.characters() }),
      ]);
    },
  });
}

export function useLinkProjectCharacterMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, characterId }: ProjectCharacterRequest) =>
      apiFetch<void>(buildProjectCharacterPath(projectId, characterId), { method: "PUT" }),
    onSuccess: () => invalidateProjectsAndCharacters(queryClient),
  });
}

export function useUnlinkProjectCharacterMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, characterId }: ProjectCharacterRequest) =>
      apiFetch<void>(buildProjectCharacterPath(projectId, characterId), { method: "DELETE" }),
    onSuccess: () => invalidateProjectsAndCharacters(queryClient),
  });
}

export function useGenerateCharacterReferenceMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, characterId }: ProjectCharacterRequest) =>
      apiFetch<GenerationRequest>(`${buildProjectCharacterPath(projectId, characterId)}/generate-reference`, {
        method: "POST",
      }),
    onSuccess: () => invalidateProjectsAndCharacters(queryClient),
  });
}

export function useEditCharacterReferenceMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, characterId, prompt }: EditCharacterReferenceRequest) =>
      apiFetch<GenerationRequest>(`${buildProjectCharacterPath(projectId, characterId)}/edit-reference`, {
        method: "POST",
        body: JSON.stringify({ prompt }),
      }),
    onSuccess: () => invalidateProjectsAndCharacters(queryClient),
  });
}

export function useGenerateMissingReferencesMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (projectId: string) =>
      apiFetch<GenerationRequest[]>(`${buildProjectPath(projectId)}/characters/generate-missing`, { method: "POST" }),
    onSuccess: () => invalidateProjectsAndCharacters(queryClient),
  });
}

export function useFilmCharactersQuery() {
  return useQuery({
    queryKey: filmQueryKeys.characterList(),
    queryFn: ({ signal }) => apiFetch<FilmCharacter[]>(`${FILMS_API_PATH}/characters`, { signal }),
  });
}

export function useFilmCharacterQuery(characterId: string) {
  return useQuery({
    queryKey: filmQueryKeys.characterDetail(characterId),
    queryFn: ({ signal }) => apiFetch<FilmCharacterDetail>(buildCharacterPath(characterId), { signal }),
  });
}

export function useCreateFilmCharacterMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (fields: CharacterFields) =>
      apiFetch<FilmCharacter>(`${FILMS_API_PATH}/characters`, { method: "POST", body: JSON.stringify(fields) }),
    onSuccess: () => invalidateProjectsAndCharacters(queryClient),
  });
}

export function useUpdateFilmCharacterMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ characterId, changes }: UpdateCharacterRequest) =>
      apiFetch<FilmCharacter>(buildCharacterPath(characterId), { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: () => invalidateProjectsAndCharacters(queryClient),
  });
}

export function useDeleteFilmCharacterMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (characterId: string) => apiFetch<void>(buildCharacterPath(characterId), { method: "DELETE" }),
    onSuccess: () => invalidateProjectsAndCharacters(queryClient),
  });
}

export function useUploadCharacterReferenceMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ characterId, file }: UploadCharacterReferenceRequest) =>
      apiUpload<FilmCharacter>(`${buildCharacterPath(characterId)}/reference`, { body: buildFileFormData(file) }),
    onSuccess: () => invalidateProjectsAndCharacters(queryClient),
  });
}

export function useFilmStylesQuery() {
  return useQuery({
    queryKey: filmQueryKeys.styles(),
    queryFn: ({ signal }) => apiFetch<FilmStyle[]>(`${FILMS_API_PATH}/styles`, { signal }),
  });
}

export function useCreateFilmStyleMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (fields: StyleFields) =>
      apiFetch<FilmStyle>(`${FILMS_API_PATH}/styles`, { method: "POST", body: JSON.stringify(fields) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filmQueryKeys.styles() }),
  });
}

export function useUpdateFilmStyleMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ styleId, changes }: UpdateStyleRequest) =>
      apiFetch<FilmStyle>(buildStylePath(styleId), { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: () => invalidateStyleUsers(queryClient),
  });
}

export function useDeleteFilmStyleMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (styleId: string) => apiFetch<void>(buildStylePath(styleId), { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filmQueryKeys.styles() }),
  });
}

export function useFilmVoicesQuery() {
  return useQuery({
    queryKey: filmQueryKeys.voices(),
    queryFn: ({ signal }) => apiFetch<VoiceTemplate[]>(`${FILMS_API_PATH}/voices`, { signal }),
  });
}

export function useCreateFilmVoiceMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: CreateVoiceRequest) =>
      apiUpload<VoiceTemplate>(`${FILMS_API_PATH}/voices`, { body: buildVoiceFormData(request) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filmQueryKeys.voices() }),
  });
}

export function useUpdateFilmVoiceMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ voiceId, changes }: UpdateVoiceRequest) =>
      apiFetch<VoiceTemplate>(buildVoicePath(voiceId), { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filmQueryKeys.voices() }),
  });
}

export function useDeleteFilmVoiceMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (voiceId: string) => apiFetch<void>(buildVoicePath(voiceId), { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filmQueryKeys.voices() }),
  });
}

export function useUploadVoiceConsentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ voiceId, file }: UploadVoiceConsentRequest) =>
      apiUpload<VoiceTemplate>(`${buildVoicePath(voiceId)}/consent`, { body: buildFileFormData(file) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filmQueryKeys.voices() }),
  });
}

export function useRemoveVoiceConsentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (voiceId: string) => apiFetch<void>(`${buildVoicePath(voiceId)}/consent`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filmQueryKeys.voices() }),
  });
}

export function useCreateFilmEpisodeMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, fields, captchaToken }: CreateEpisodeRequest) =>
      apiFetch<Episode>(`${buildProjectPath(projectId)}/episodes`, {
        method: "POST",
        body: JSON.stringify(fields),
        headers: buildCaptchaHeaders(captchaToken),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filmQueryKeys.projects() }),
  });
}

export function useFilmEpisodeQuery(episodeId: string) {
  return useQuery({
    queryKey: filmQueryKeys.episodeDetail(episodeId),
    queryFn: ({ signal }) => apiFetch<EpisodeDetail>(buildEpisodePath(episodeId), { signal }),
    refetchInterval: (query) => {
      const episode = query.state.data;
      return episode && isFilmEpisodeBusy(episode) ? FILM_STUDIO_REFRESH_INTERVAL_MS : false;
    },
  });
}

export function useUpdateFilmEpisodeMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ episodeId, changes }: UpdateEpisodeRequest) =>
      apiFetch<Episode>(buildEpisodePath(episodeId), { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: () => invalidateEpisodesAndProjects(queryClient),
  });
}

export function useDeleteFilmEpisodeMutation(onDeleted: () => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (episodeId: string) => apiFetch<void>(buildEpisodePath(episodeId), { method: "DELETE" }),
    onSuccess: () => {
      onDeleted();
      return queryClient.invalidateQueries({ queryKey: filmQueryKeys.projects() });
    },
  });
}

export function useEpisodeActionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: filmMutationKeys.episodeActions(),
    mutationFn: ({ episodeId, action }: EpisodeActionRequest) =>
      apiFetch<Episode>(`${buildEpisodePath(episodeId)}/${action}`, { method: "POST" }),
    onSuccess: () => invalidateEpisodesAndProjects(queryClient),
  });
}

export function useLatestEpisodeActionError(episodeId: string): Error | null {
  const actionErrors = useMutationState({
    filters: {
      mutationKey: filmMutationKeys.episodeActions(),
      predicate: (mutation) => isActionOfEpisode(mutation.state.variables, episodeId),
    },
    select: (mutation) => mutation.state.error,
  });
  return actionErrors.at(-1) ?? null;
}

export function useGenerateThumbnailsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (episodeId: string) =>
      apiFetch<GenerationRequest[]>(`${buildEpisodePath(episodeId)}/thumbnails`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filmQueryKeys.episodes() }),
  });
}

export function useChooseThumbnailMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ episodeId, candidate }: ChooseThumbnailRequest) =>
      apiFetch<Episode>(`${buildEpisodePath(episodeId)}/thumbnail`, {
        method: "POST",
        body: JSON.stringify({ candidate }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filmQueryKeys.episodes() }),
  });
}

export function useCreateFilmSceneMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ episodeId, afterPosition, fields }: CreateSceneRequest) =>
      apiFetch<Scene>(`${buildEpisodePath(episodeId)}/scenes`, {
        method: "POST",
        body: JSON.stringify({ ...fields, afterPosition }),
      }),
    onSuccess: () => invalidateEpisodesAndProjects(queryClient),
  });
}

export function useUpdateFilmSceneMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sceneId, changes }: UpdateSceneRequest) =>
      apiFetch<Scene>(buildScenePath(sceneId), { method: "PATCH", body: JSON.stringify(changes) }),
    onSuccess: () => invalidateEpisodesAndProjects(queryClient),
  });
}

export function useDeleteFilmSceneMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sceneId: string) => apiFetch<void>(buildScenePath(sceneId), { method: "DELETE" }),
    onSuccess: () => invalidateEpisodesAndProjects(queryClient),
  });
}

export function useUploadSceneImageMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sceneId, file }: UploadSceneImageRequest) =>
      apiUpload<Scene>(`${buildScenePath(sceneId)}/image`, { body: buildFileFormData(file) }),
    onSuccess: () => invalidateEpisodesAndProjects(queryClient),
  });
}

export function useGenerateSceneMediaMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sceneId, action }: GenerateSceneMediaRequest) =>
      apiFetch<GenerationRequest>(`${buildScenePath(sceneId)}/${action}`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filmQueryKeys.episodes() }),
  });
}

export function useEditSceneImageMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sceneId, prompt }: EditSceneImageRequest) =>
      apiFetch<GenerationRequest>(`${buildScenePath(sceneId)}/edit-image`, {
        method: "POST",
        body: JSON.stringify({ prompt }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filmQueryKeys.episodes() }),
  });
}

export function useCancelFilmRequestMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (requestId: string) =>
      apiFetch<GenerationRequest>(`${FILMS_API_PATH}/requests/${encodeURIComponent(requestId)}/cancel`, {
        method: "POST",
      }),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: filmQueryKeys.episodes() }),
        queryClient.invalidateQueries({ queryKey: filmQueryKeys.projects() }),
        queryClient.invalidateQueries({ queryKey: filmQueryKeys.characters() }),
      ]),
  });
}

function useProjectStatusMutation(statusAction: "archive" | "unarchive") {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (projectId: string) =>
      apiFetch<FilmProject>(`${buildProjectPath(projectId)}/${statusAction}`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: filmQueryKeys.projects() }),
  });
}

function invalidateProjectsAndCharacters(queryClient: QueryClient): Promise<void[]> {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: filmQueryKeys.projects() }),
    queryClient.invalidateQueries({ queryKey: filmQueryKeys.characters() }),
  ]);
}

function invalidateEpisodesAndProjects(queryClient: QueryClient): Promise<void[]> {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: filmQueryKeys.episodes() }),
    queryClient.invalidateQueries({ queryKey: filmQueryKeys.projects() }),
  ]);
}

function invalidateStyleUsers(queryClient: QueryClient): Promise<void[]> {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: filmQueryKeys.styles() }),
    queryClient.invalidateQueries({ queryKey: filmQueryKeys.projects() }),
    queryClient.invalidateQueries({ queryKey: filmQueryKeys.characters() }),
  ]);
}

function isActionOfEpisode(variables: unknown, episodeId: string): boolean {
  return typeof variables === "object" && variables !== null && "episodeId" in variables && variables.episodeId === episodeId;
}

function fetchFilmProjects(status: ProjectStatus, signal: AbortSignal): Promise<FilmProject[]> {
  const searchParams = new URLSearchParams({ status });
  return apiFetch<FilmProject[]>(`${FILMS_API_PATH}/projects?${searchParams.toString()}`, { signal });
}

function buildFileFormData(file: File): FormData {
  const formData = new FormData();
  formData.append("file", file);
  return formData;
}

function buildVoiceFormData(request: CreateVoiceRequest): FormData {
  const formData = buildFileFormData(request.file);
  formData.append("name", request.name);
  if (request.sampleText.trim()) formData.append("sampleText", request.sampleText);
  if (request.description.trim()) formData.append("description", request.description);
  return formData;
}

function buildProjectPath(projectId: string): string {
  return `${FILMS_API_PATH}/projects/${encodeURIComponent(projectId)}`;
}

function buildProjectCharacterPath(projectId: string, characterId: string): string {
  return `${buildProjectPath(projectId)}/characters/${encodeURIComponent(characterId)}`;
}

function buildCharacterPath(characterId: string): string {
  return `${FILMS_API_PATH}/characters/${encodeURIComponent(characterId)}`;
}

function buildStylePath(styleId: string): string {
  return `${FILMS_API_PATH}/styles/${encodeURIComponent(styleId)}`;
}

function buildVoicePath(voiceId: string): string {
  return `${FILMS_API_PATH}/voices/${encodeURIComponent(voiceId)}`;
}

function buildEpisodePath(episodeId: string): string {
  return `${FILMS_API_PATH}/episodes/${encodeURIComponent(episodeId)}`;
}

function buildScenePath(sceneId: string): string {
  return `${FILMS_API_PATH}/scenes/${encodeURIComponent(sceneId)}`;
}

function buildCaptchaHeaders(captchaToken: string | undefined): Record<string, string> {
  return captchaToken ? { [CAPTCHA_TOKEN_HEADER]: captchaToken } : {};
}
