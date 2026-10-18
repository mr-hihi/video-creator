import {
  COMPLETED_JOB_STEP_LABEL,
  JOB_STEP_LABELS,
  MISSING_OUTPUT_MESSAGE,
  WAITING_OUTPUT_MESSAGE,
} from "@/features/jobs/constants";
import type { JobStepState } from "@/features/jobs/types";
import { buildApiUrl, buildJobFileUrl } from "@/lib/api/client";
import { DEFAULT_INPUT_MODE } from "@/features/settings/constants";
import { joinAiUsedDescriptions, listAiUsedDescriptions } from "@/features/settings/utils";
import {
  CLONE_AI_STEPS,
  CLONE_JOB_STEPS_BY_INPUT_MODE,
  CLONE_MAX_FRAMES_LOWER_LIMIT,
  CLONE_MAX_FRAMES_UPPER_LIMIT,
  CLONE_STAGE_LABELS,
  CLONE_TABS,
  EMPTY_VALUE_LABEL,
  FAILED_IMAGE_LABEL_PREFIX,
  FILM_CLONE_PATH,
  FILM_CLONE_STEP_LABELS,
  FOLLOW_TARGET_COUNTRY_SETTING,
  GENERATE_IMAGE_LABEL,
  GENERATING_IMAGE_LABEL,
  LOCALIZATION_FLAGS,
  ORIGINAL_SETTING_LABEL,
  QUEUED_IMAGE_LABEL,
  REGENERATE_IMAGE_LABEL,
  SCRIPT_LANGUAGE_NAMES,
  TARGET_COUNTRIES,
  UNTICKED_LOCALIZATION_FLAGS,
  type CloneTab,
  type TargetCountry,
} from "./constants";
import type {
  AiActivity,
  AssetKind,
  AutomaticRunChoices,
  CloneAspect,
  CloneAsset,
  CloneImageOrientation,
  CloneImageStatus,
  CloneJob,
  CloneJobStep,
  CloneScene,
  CloneShot,
  CloneStage,
  CloneStageState,
  FilmClone,
  FilmCloneDetail,
  FilmCloneStatus,
  FilmCloneStep,
  GenerationRequest,
  LocalizationChoices,
  LocalizationFlags,
  LocalizedAssetChanges,
  LocalizedAssetDraft,
  OriginalAssetChanges,
  SceneChanges,
  ScriptLanguageCode,
  TargetCountryCode,
} from "./types";
import type { ScriptLanguage } from "@/features/settings/types";

const FINISHED_CLONE_STATUSES: ReadonlySet<FilmCloneStatus> = new Set(["done", "failed"]);
const LATER_CLONE_STEPS: ReadonlySet<FilmCloneStep> = new Set(["proposing", "writing_script", "generating_scene_images"]);
const RESUMABLE_CLONE_STEPS: ReadonlySet<FilmCloneStep> = new Set([
  "extracting_assets",
  "analyzing_shots",
  ...LATER_CLONE_STEPS,
]);
const ANALYSIS_CLONE_STEPS: ReadonlySet<FilmCloneStep> = new Set(["analyzing", "extracting_assets", "analyzing_shots"]);
const BUSY_IMAGE_STATUSES: ReadonlySet<CloneImageStatus> = new Set(["queued", "processing"]);
const STAGE_INDEX_BY_STEP: Record<FilmCloneStep, number> = {
  analyzing: 0,
  extracting_assets: 1,
  analyzing_shots: 1,
  choosing_localization: 2,
  proposing: 2,
  reviewing: 2,
  writing_script: 3,
  generating_scene_images: 3,
};
const STAGE_STATE_BY_CLONE_STATUS: Record<FilmCloneStatus, CloneStageState> = {
  running: "current",
  waiting: "waiting",
  failed: "failed",
  done: "completed",
};
const TARGET_COUNTRIES_BY_CODE: ReadonlyMap<TargetCountryCode, TargetCountry> = new Map(
  TARGET_COUNTRIES.map((country) => [country.code, country]),
);
const PORTRAIT_ASPECT: CloneAspect = "9:16";
const LANDSCAPE_REFERENCE_KINDS: ReadonlySet<AssetKind> = new Set(["location"]);
const TRANSCRIPT_LANGUAGE_PATTERN = /· Language: ([A-Za-z-]+)\s*$/m;
const TRANSCRIPT_LANGUAGE_MAX_LENGTH = 3;
const MS_PER_SECOND = 1_000;
const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3_600;
const CLOCK_PART_LENGTH = 2;
const YOUTUBE_WATCH_URL_PREFIX = "https://www.youtube.com/watch?v=";
const CLONE_FILES_PATH = "/film-clones/files";
const MARKDOWN_BLOCK_SEPARATOR = "\n\n";

export function isValidCloneMaxFrames(maxFrames: number): boolean {
  return (
    Number.isInteger(maxFrames) && maxFrames >= CLONE_MAX_FRAMES_LOWER_LIMIT && maxFrames <= CLONE_MAX_FRAMES_UPPER_LIMIT
  );
}

export function isFilmCloneBusy(clone: Pick<FilmClone, "status" | "hasOpenRequests">): boolean {
  return clone.status === "running" || clone.hasOpenRequests;
}

export function hasBusyFilmClone(clones: readonly Pick<FilmClone, "status" | "hasOpenRequests">[]): boolean {
  return clones.some(isFilmCloneBusy);
}

export function isFilmCloneFinished(clone: Pick<FilmClone, "status">): boolean {
  return FINISHED_CLONE_STATUSES.has(clone.status);
}

export function isCloneWaitingAt(clone: Pick<FilmClone, "status" | "step">, step: FilmCloneStep): boolean {
  return clone.status === "waiting" && clone.step === step;
}

export function canResumeFilmClone(clone: Pick<FilmClone, "status" | "step">): boolean {
  return clone.status === "failed" && RESUMABLE_CLONE_STEPS.has(clone.step);
}

export function canRelocalizeFilmClone(clone: Pick<FilmClone, "status" | "step">): boolean {
  return (
    isCloneWaitingAt(clone, "reviewing") ||
    clone.status === "done" ||
    (clone.status === "failed" && LATER_CLONE_STEPS.has(clone.step))
  );
}

export function isFilmCloneAnalyzing(clone: Pick<FilmClone, "step">): boolean {
  return ANALYSIS_CLONE_STEPS.has(clone.step);
}

export function describeAiActivity(activity: AiActivity, nowMs: number): string {
  const workingLabel = `${activity.label} is working`;
  const elapsed = formatTimestamp(Math.max(0, nowMs - Date.parse(activity.startedAt)));
  if (activity.lastOutputAt === null) return `${workingLabel} · ${elapsed} · no output yet`;
  const silentSeconds = Math.max(0, Math.floor((nowMs - Date.parse(activity.lastOutputAt)) / MS_PER_SECOND));
  return `${workingLabel} · ${elapsed} · last output ${silentSeconds}s ago`;
}

export function describeCloneAiUsed(clone: Pick<FilmCloneDetail, "aiUsed" | "job">): string {
  const jobDescriptions = clone.job
    ? listAiUsedDescriptions(clone.job.aiUsed, listCloneJobSteps(clone.job), JOB_STEP_LABELS)
    : [];
  const cloneDescriptions = listAiUsedDescriptions(clone.aiUsed, CLONE_AI_STEPS, FILM_CLONE_STEP_LABELS);
  return joinAiUsedDescriptions([...jobDescriptions, ...cloneDescriptions]);
}

export function canEditCloneScenes(clone: Pick<FilmClone, "status" | "step">): boolean {
  return clone.status === "done" || (clone.status === "failed" && clone.step === "generating_scene_images");
}

export function describeFilmCloneStep(clone: Pick<FilmClone, "status" | "step">): string {
  if (clone.status === "done") return COMPLETED_JOB_STEP_LABEL;
  return FILM_CLONE_STEP_LABELS[clone.step];
}

export function describeTargetCountry(countryCode: TargetCountryCode | null): string {
  if (countryCode === null) return ORIGINAL_SETTING_LABEL;
  return TARGET_COUNTRIES_BY_CODE.get(countryCode)?.name ?? countryCode;
}

export function describeScriptLanguage(languageCode: string | null): string {
  if (languageCode === null) return EMPTY_VALUE_LABEL;
  return isScriptLanguageCode(languageCode) ? SCRIPT_LANGUAGE_NAMES[languageCode] : languageCode;
}

export function determineCloneStages(clone: Pick<FilmClone, "status" | "step">): CloneStage[] {
  const activeStageIndex = STAGE_INDEX_BY_STEP[clone.step];
  const activeStageState = STAGE_STATE_BY_CLONE_STATUS[clone.status];
  return CLONE_STAGE_LABELS.map((label, stageIndex) => {
    if (clone.status === "done" || stageIndex < activeStageIndex) return { label, state: "completed" };
    if (stageIndex > activeStageIndex) return { label, state: "upcoming" };
    return { label, state: activeStageState };
  });
}

export function listCloneJobSteps(job: Pick<CloneJob, "type" | "options">): readonly CloneJobStep[] {
  return CLONE_JOB_STEPS_BY_INPUT_MODE[job.options.inputMode ?? DEFAULT_INPUT_MODE][job.type];
}

export function determineCloneJobStepState(
  job: Pick<CloneJob, "type" | "status" | "step" | "options">,
  step: CloneJobStep,
): JobStepState {
  if (job.status === "done") return "completed";
  if (job.step === null) return "upcoming";
  const jobSteps = listCloneJobSteps(job);
  const stepIndex = jobSteps.indexOf(step);
  const currentStepIndex = jobSteps.indexOf(job.step);
  if (stepIndex < currentStepIndex) return "completed";
  if (stepIndex > currentStepIndex) return "upcoming";
  return job.status === "failed" ? "failed" : "current";
}

export function buildFilmCloneDetailPath(cloneId: string): string {
  return `${FILM_CLONE_PATH}/${encodeURIComponent(cloneId)}`;
}

export function buildCloneFrameUrl(jobId: string, frame: string): string {
  return buildJobFileUrl(jobId, frame);
}

export function buildCloneFileUrl(relativePath: string, imageVersion: number): string {
  const encodedPath = relativePath.split("/").map(encodeURIComponent).join("/");
  return buildApiUrl(`${CLONE_FILES_PATH}/${encodedPath}?v=${imageVersion}`);
}

export function formatTimestamp(positionMs: number): string {
  const totalSeconds = Math.floor(positionMs / MS_PER_SECOND);
  const hours = Math.floor(totalSeconds / SECONDS_PER_HOUR);
  const minutes = Math.floor((totalSeconds % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE);
  const seconds = totalSeconds % SECONDS_PER_MINUTE;
  const clock = `${padClockPart(minutes)}:${padClockPart(seconds)}`;
  return hours ? `${hours}:${clock}` : clock;
}

export function buildYoutubeTimestampUrl(videoId: string, positionMs: number): string {
  return `${YOUTUBE_WATCH_URL_PREFIX}${encodeURIComponent(videoId)}&t=${Math.floor(positionMs / MS_PER_SECOND)}s`;
}

export function findTranscriptLanguage(videoNotes: string | null): string | null {
  const match = videoNotes?.match(TRANSCRIPT_LANGUAGE_PATTERN);
  return match ? match[1].toLowerCase().slice(0, TRANSCRIPT_LANGUAGE_MAX_LENGTH) : null;
}

export function resolveScriptLanguage(
  setting: ScriptLanguage,
  targetCountry: TargetCountryCode | null,
  transcriptLanguage: string | null,
): string | null {
  if (setting !== FOLLOW_TARGET_COUNTRY_SETTING) return setting;
  if (targetCountry === null) return transcriptLanguage;
  return TARGET_COUNTRIES_BY_CODE.get(targetCountry)?.language ?? null;
}

export function hasTickedLocalizationFlag(flags: LocalizationFlags): boolean {
  return LOCALIZATION_FLAGS.some((flag) => flags[flag.key]);
}

export function clearFlagsWithoutCountry(choices: LocalizationChoices): LocalizationChoices {
  return choices.targetCountry ? choices : { ...choices, ...UNTICKED_LOCALIZATION_FLAGS };
}

export function resolveAutomaticChoices(automaticRun: AutomaticRunChoices): LocalizationChoices | undefined {
  return automaticRun.shouldRunAutomatically ? clearFlagsWithoutCountry(automaticRun.choices) : undefined;
}

export function flagsToCandidateKinds(flags: LocalizationFlags): ReadonlySet<AssetKind> {
  return new Set(LOCALIZATION_FLAGS.filter((flag) => flags[flag.key]).flatMap((flag) => flag.kinds));
}

export function describeAssetName(asset: Pick<CloneAsset, "changed" | "name" | "localizedName">): string {
  return asset.changed && asset.localizedName ? asset.localizedName : asset.name;
}

export function findAssetsByIds(assetIds: readonly string[], assets: readonly CloneAsset[]): CloneAsset[] {
  const assetsById = new Map(assets.map((asset) => [asset.id, asset]));
  return assetIds.flatMap((assetId) => assetsById.get(assetId) ?? []);
}

export function isAssetGenerating(asset: CloneAsset, openRequests: readonly GenerationRequest[]): boolean {
  return BUSY_IMAGE_STATUSES.has(asset.referenceStatus) || openRequests.some((request) => request.cloneAssetId === asset.id);
}

export function isSceneGenerating(scene: CloneScene, openRequests: readonly GenerationRequest[]): boolean {
  return BUSY_IMAGE_STATUSES.has(scene.imageStatus) || openRequests.some((request) => request.cloneSceneId === scene.id);
}

export function describeGenerateAction(imageStatus: CloneImageStatus): string {
  return imageStatus === "none" ? GENERATE_IMAGE_LABEL : REGENERATE_IMAGE_LABEL;
}

export function describeImageProgress(imageStatus: CloneImageStatus, imageError: string | null): string | undefined {
  if (imageStatus === "queued") return QUEUED_IMAGE_LABEL;
  if (imageStatus === "processing") return GENERATING_IMAGE_LABEL;
  if (imageStatus === "failed") return `${FAILED_IMAGE_LABEL_PREFIX}${imageError ?? EMPTY_VALUE_LABEL}`;
  return undefined;
}

export function aspectToFrameOrientation(aspect: CloneAspect | null): CloneImageOrientation {
  return aspect === PORTRAIT_ASPECT ? "portrait" : "landscape";
}

export function kindToReferenceOrientation(kind: AssetKind): CloneImageOrientation {
  return LANDSCAPE_REFERENCE_KINDS.has(kind) ? "landscape" : "portrait";
}

export function describeSceneNumber(scene: Pick<CloneScene, "position">): string {
  return `Scene ${scene.position + 1}`;
}

export function describeShotTimestamp(shot: CloneShot | undefined): string {
  return shot ? formatTimestamp(shot.atMs) : EMPTY_VALUE_LABEL;
}

export function buildScriptMarkdown(clone: Pick<FilmCloneDetail, "scriptTitle" | "logline" | "scenes" | "shots">): string {
  const shotsById = new Map(clone.shots.map((shot) => [shot.id, shot]));
  const sceneBlocks = clone.scenes.flatMap((scene) => [
    `## ${describeSceneNumber(scene)} — ${describeShotTimestamp(shotsById.get(scene.shotId))}`,
    scene.description,
    ...(scene.dialogue ? [scene.dialogue] : []),
  ]);
  const headerBlocks = [`# ${clone.scriptTitle ?? ""}`, ...(clone.logline ? [clone.logline] : [])];
  return [...headerBlocks, ...sceneBlocks].join(MARKDOWN_BLOCK_SEPARATOR);
}

export function buildDeleteAssetConfirmation(assetName: string): string {
  return `Delete asset '${assetName}'?`;
}

export function describeFrameCount(frames: readonly string[]): string {
  return `${frames.length} frames`;
}

export function hasCloneTabContent(clone: FilmCloneDetail, tab: CloneTab): boolean {
  if (tab === "videoNotes") return clone.videoNotes !== null;
  if (tab === "assets") return clone.assets.length > 0;
  if (tab === "shots") return clone.shots.length > 0 && !isFilmCloneAnalyzing(clone);
  if (tab === "localization") return !isFilmCloneAnalyzing(clone);
  return clone.scenes.length > 0;
}

export function findFirstCloneTabWithContent(clone: FilmCloneDetail): CloneTab {
  const filledTab = CLONE_TABS.find((tab) => hasCloneTabContent(clone, tab.value));
  return filledTab?.value ?? CLONE_TABS[0].value;
}

export function describeMissingCloneContent(clone: Pick<FilmClone, "status">): string {
  return isFilmCloneFinished(clone) ? MISSING_OUTPUT_MESSAGE : WAITING_OUTPUT_MESSAGE;
}

export function assetToOriginalDraft(asset: CloneAsset): OriginalAssetChanges {
  return {
    name: asset.name,
    kind: asset.kind,
    description: asset.description,
    culture: asset.culture,
    period: asset.period,
  };
}

export function assetToLocalizedDraft(asset: CloneAsset): LocalizedAssetDraft {
  return {
    localizedName: asset.localizedName ?? "",
    localizedDescription: asset.localizedDescription ?? "",
  };
}

export function buildLocalizedAssetChanges(
  draft: LocalizedAssetDraft,
  asset: Pick<CloneAsset, "changed">,
): LocalizedAssetChanges {
  return {
    ...(asset.changed ? {} : { changed: true }),
    ...(draft.localizedName.trim() ? { localizedName: draft.localizedName } : {}),
    localizedDescription: draft.localizedDescription,
  };
}

export function sceneToDraft(scene: CloneScene): SceneChanges {
  return {
    description: scene.description,
    dialogue: scene.dialogue ?? "",
    imagePrompt: scene.imagePrompt,
  };
}

export function haveSameFieldValues<TFields extends object>(first: TFields, second: TFields): boolean {
  return (Object.keys(first) as (keyof TFields)[]).every((field) => first[field] === second[field]);
}

export function labelsToSelectOptions<TValue extends string>(
  labelsByValue: Record<TValue, string>,
): { value: TValue; label: string }[] {
  return (Object.entries(labelsByValue) as [TValue, string][]).map(([value, label]) => ({ value, label }));
}

function isScriptLanguageCode(languageCode: string): languageCode is ScriptLanguageCode {
  return Object.hasOwn(SCRIPT_LANGUAGE_NAMES, languageCode);
}

function padClockPart(value: number): string {
  return String(value).padStart(CLOCK_PART_LENGTH, "0");
}
