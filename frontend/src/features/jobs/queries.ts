import { useIsMutating, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, apiUpload } from "@/lib/api/client";
import type { UploadLanguage } from "./constants";
import type { Job, JobDetail, JobType } from "./types";
import { hasJobInProgress, isJobInProgress } from "./utils";

const JOB_LIST_LIMIT = 50;
const JOB_POLL_INTERVAL_MS = 3_000;
const YOUTUBE_JOB_REQUEST_TIMEOUT_MS = 45_000;
const CAPTCHA_TOKEN_HEADER = "X-Captcha-Token";

export interface CreateVideoToMarkdownJobRequest {
  file: File;
  language: UploadLanguage;
  presetId?: string;
  captchaToken?: string;
  onUploadProgress: (uploadedPercent: number) => void;
}

export interface CreateYoutubeToMarkdownJobRequest {
  url: string;
  language: UploadLanguage;
  presetId?: string;
  captchaToken?: string;
}

export interface CreateFilmAnalysisJobRequest extends CreateVideoToMarkdownJobRequest {
  maxFrames?: number;
}

export interface CreateYoutubeFilmAnalysisJobRequest extends CreateYoutubeToMarkdownJobRequest {
  maxFrames?: number;
}

export interface CreateFilmAnalysisRerunJobRequest {
  sourceJobId: string;
  presetId?: string;
  captchaToken?: string;
}

export const jobQueryKeys = {
  all: ["jobs"] as const,
  lists: () => [...jobQueryKeys.all, "list"] as const,
  list: (types: readonly JobType[], limit: number) => [...jobQueryKeys.lists(), types, limit] as const,
  detail: (jobId: string) => [...jobQueryKeys.all, "detail", jobId] as const,
};

const jobMutationKeys = {
  creations: () => [...jobQueryKeys.all, "create"] as const,
};

export function useJobsQuery(types: readonly JobType[]) {
  return useQuery({
    queryKey: jobQueryKeys.list(types, JOB_LIST_LIMIT),
    queryFn: ({ signal }) => fetchJobs(types, JOB_LIST_LIMIT, signal),
    refetchInterval: (query) => (hasJobInProgress(query.state.data ?? []) ? JOB_POLL_INTERVAL_MS : false),
  });
}

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

export function useCreateVideoToMarkdownJobMutation() {
  return useJobCreationMutation(createVideoToMarkdownJob);
}

export function useCreateYoutubeToMarkdownJobMutation() {
  return useJobCreationMutation(createYoutubeToMarkdownJob);
}

export function useCreateFilmAnalysisJobMutation() {
  return useJobCreationMutation(createFilmAnalysisJob);
}

export function useCreateYoutubeFilmAnalysisJobMutation() {
  return useJobCreationMutation(createYoutubeFilmAnalysisJob);
}

export function useCreateFilmAnalysisRerunJobMutation() {
  return useJobCreationMutation(createFilmAnalysisRerunJob);
}

export function useDeleteJobMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => apiFetch<void>(buildJobPath(jobId), { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: jobQueryKeys.lists() }),
  });
}

export function useIsCreatingJob(): boolean {
  return useIsMutating({ mutationKey: jobMutationKeys.creations() }) > 0;
}

function useJobCreationMutation<TRequest>(mutationFn: (request: TRequest) => Promise<Job>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: jobMutationKeys.creations(),
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: jobQueryKeys.lists() }),
  });
}

function fetchJobs(types: readonly JobType[], limit: number, signal: AbortSignal): Promise<Job[]> {
  const searchParams = new URLSearchParams({ limit: String(limit) });
  types.forEach((type) => searchParams.append("type", type));
  return apiFetch<Job[]>(`/jobs?${searchParams.toString()}`, { signal });
}

function fetchJob(jobId: string, signal: AbortSignal): Promise<JobDetail> {
  return apiFetch<JobDetail>(buildJobPath(jobId), { signal });
}

function createVideoToMarkdownJob(request: CreateVideoToMarkdownJobRequest): Promise<Job> {
  return uploadJobSource("/jobs/video-to-markdown", buildUploadFormData(request), request);
}

function createFilmAnalysisJob(request: CreateFilmAnalysisJobRequest): Promise<Job> {
  const formData = buildUploadFormData(request);
  if (request.maxFrames !== undefined) formData.append("maxFrames", String(request.maxFrames));
  return uploadJobSource("/jobs/film-analysis", formData, request);
}

function createYoutubeToMarkdownJob(request: CreateYoutubeToMarkdownJobRequest): Promise<Job> {
  return postYoutubeJob("/jobs/youtube-to-markdown", request, {
    url: request.url,
    language: request.language,
    presetId: request.presetId,
  });
}

function createYoutubeFilmAnalysisJob(request: CreateYoutubeFilmAnalysisJobRequest): Promise<Job> {
  return postYoutubeJob("/jobs/youtube-film-analysis", request, {
    url: request.url,
    language: request.language,
    presetId: request.presetId,
    maxFrames: request.maxFrames,
  });
}

function createFilmAnalysisRerunJob(request: CreateFilmAnalysisRerunJobRequest): Promise<Job> {
  return apiFetch<Job>(`${buildJobPath(request.sourceJobId)}/film-analysis-rerun`, {
    method: "POST",
    body: JSON.stringify({ presetId: request.presetId }),
    headers: buildCaptchaHeaders(request.captchaToken),
  });
}

function buildUploadFormData(request: CreateVideoToMarkdownJobRequest): FormData {
  const formData = new FormData();
  formData.append("file", request.file);
  formData.append("language", request.language);
  if (request.presetId) formData.append("presetId", request.presetId);
  return formData;
}

function uploadJobSource(path: string, formData: FormData, request: CreateVideoToMarkdownJobRequest): Promise<Job> {
  return apiUpload<Job>(path, {
    body: formData,
    headers: buildCaptchaHeaders(request.captchaToken),
    onUploadProgress: request.onUploadProgress,
  });
}

function postYoutubeJob(path: string, request: CreateYoutubeToMarkdownJobRequest, body: object): Promise<Job> {
  return apiFetch<Job>(path, {
    method: "POST",
    body: JSON.stringify(body),
    headers: buildCaptchaHeaders(request.captchaToken),
    timeoutMs: YOUTUBE_JOB_REQUEST_TIMEOUT_MS,
  });
}

function buildJobPath(jobId: string): string {
  return `/jobs/${encodeURIComponent(jobId)}`;
}

function buildCaptchaHeaders(captchaToken: string | undefined): Record<string, string> {
  return captchaToken ? { [CAPTCHA_TOKEN_HEADER]: captchaToken } : {};
}
