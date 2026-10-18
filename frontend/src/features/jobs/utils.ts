import { DEFAULT_INPUT_MODE } from "@/features/settings/constants";
import { describeInputMode, joinAiUsedDescriptions, listAiUsedDescriptions } from "@/features/settings/utils";
import { buildJobFileUrl } from "@/lib/api/client";
import {
  CAPTION_KIND_LABELS,
  COMPLETED_JOB_STEP_LABEL,
  FILM_ANALYSIS_JOB_TYPES,
  JOB_STEP_LABELS,
  JOB_STEPS_BY_INPUT_MODE,
  MAX_FRAMES_LOWER_LIMIT,
  MAX_FRAMES_UPPER_LIMIT,
  NOT_STARTED_JOB_STEP_LABEL,
  UNKNOWN_CAPTION_KIND_LABEL,
  UPLOAD_LANGUAGE_OPTIONS,
} from "./constants";
import type { CaptionKind, FrameCounts, Job, JobDetail, JobOutputs, JobStatus, JobStep, JobStepState } from "./types";

const IN_PROGRESS_JOB_STATUSES: ReadonlySet<JobStatus> = new Set(["pending", "processing"]);
const FINISHED_JOB_STATUSES: ReadonlySet<JobStatus> = new Set(["done", "failed"]);
const FILM_ANALYSIS_JOB_TYPE_SET: ReadonlySet<Job["type"]> = new Set(FILM_ANALYSIS_JOB_TYPES);
const MISSING_FRAME_COUNTS_LABEL = "—";
const MISSING_INPUT_MODE_LABEL = "—";
const ABSOLUTE_URL_PATTERN = /^(?:[a-z][a-z\d+.-]*:|\/)/i;
const CURRENT_DIRECTORY_PREFIX = "./";

export function isJobInProgress(job: Pick<Job, "status">): boolean {
  return IN_PROGRESS_JOB_STATUSES.has(job.status);
}

export function hasJobInProgress(jobs: readonly Pick<Job, "status">[]): boolean {
  return jobs.some(isJobInProgress);
}

export function isJobFinished(job: Pick<Job, "status">): boolean {
  return FINISHED_JOB_STATUSES.has(job.status);
}

export function isFilmAnalysisJob(job: Pick<Job, "type">): boolean {
  return FILM_ANALYSIS_JOB_TYPE_SET.has(job.type);
}

export function canDeleteJob(job: Pick<Job, "type" | "status">): boolean {
  return isFilmAnalysisJob(job) && isJobFinished(job);
}

export function canRerunJob(job: Pick<JobDetail, "type" | "status" | "outputs">): boolean {
  return isFilmAnalysisJob(job) && isJobFinished(job) && Boolean(job.outputs?.videoNotes);
}

export function hasAnyJobOutput(outputs: JobOutputs | null): boolean {
  return outputs !== null && Object.values(outputs).some((output) => output !== null);
}

export function isValidMaxFrames(maxFrames: number): boolean {
  return Number.isInteger(maxFrames) && maxFrames >= MAX_FRAMES_LOWER_LIMIT && maxFrames <= MAX_FRAMES_UPPER_LIMIT;
}

export function describeFrameCounts(frameCounts: FrameCounts | undefined): string {
  if (!frameCounts) return MISSING_FRAME_COUNTS_LABEL;
  return `${frameCounts.dialogue} dialogue + ${frameCounts.scene} scene changes`;
}

export function buildJobDetailPath(jobId: string): string {
  return `/jobs/${encodeURIComponent(jobId)}`;
}

export function buildFilmAnalysisDetailPath(jobId: string): string {
  return `/film-analysis/${encodeURIComponent(jobId)}`;
}

export function describeCurrentJobStep(job: Pick<Job, "status" | "step">): string {
  if (job.status === "done") return COMPLETED_JOB_STEP_LABEL;
  if (job.step === null) return NOT_STARTED_JOB_STEP_LABEL;
  return JOB_STEP_LABELS[job.step];
}

export function listJobSteps(job: Pick<Job, "type" | "options">): readonly JobStep[] {
  return JOB_STEPS_BY_INPUT_MODE[job.options.inputMode ?? DEFAULT_INPUT_MODE][job.type];
}

export function determineJobStepState(
  job: Pick<Job, "type" | "status" | "step" | "options">,
  step: JobStep,
): JobStepState {
  if (job.status === "done") return "completed";
  if (job.step === null) return "upcoming";
  const jobSteps = listJobSteps(job);
  const stepIndex = jobSteps.indexOf(step);
  const currentStepIndex = jobSteps.indexOf(job.step);
  if (stepIndex < currentStepIndex) return "completed";
  if (stepIndex > currentStepIndex) return "upcoming";
  return job.status === "failed" ? "failed" : "current";
}

export function describeCaptionKind(captionKind: CaptionKind | undefined): string {
  return captionKind ? CAPTION_KIND_LABELS[captionKind] : UNKNOWN_CAPTION_KIND_LABEL;
}

export function describeJobAiUsed(job: Pick<Job, "type" | "options" | "aiUsed">): string {
  return joinAiUsedDescriptions(listAiUsedDescriptions(job.aiUsed, listJobSteps(job), JOB_STEP_LABELS));
}

export function describeJobInputMode(job: Pick<Job, "type" | "options">): string {
  if (job.type === "film_analysis_rerun") return MISSING_INPUT_MODE_LABEL;
  return describeInputMode(job.options.inputMode);
}

export function describeLanguage(languageCode: string): string {
  const matchingOption = UPLOAD_LANGUAGE_OPTIONS.find((option) => option.value === languageCode);
  return matchingOption?.label ?? languageCode;
}

export function resolveJobImageUrl(jobId: string, assetPath: string): string | undefined {
  if (ABSOLUTE_URL_PATTERN.test(assetPath)) return undefined;
  const relativePath = assetPath.startsWith(CURRENT_DIRECTORY_PREFIX)
    ? assetPath.slice(CURRENT_DIRECTORY_PREFIX.length)
    : assetPath;
  return buildJobFileUrl(jobId, relativePath);
}
