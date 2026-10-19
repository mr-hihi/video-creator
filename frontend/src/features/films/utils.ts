import type { GenerationRequest } from "@/features/filmClones/types";
import { buildFilmCloneDetailPath, formatTimestamp } from "@/features/filmClones/utils";
import { COMPLETED_JOB_STEP_LABEL, NOT_STARTED_JOB_STEP_LABEL } from "@/features/jobs/constants";
import type { Job } from "@/features/jobs/types";
import { buildFilmAnalysisDetailPath } from "@/features/jobs/utils";
import { joinAiUsedDescriptions, listAiUsedDescriptions } from "@/features/settings/utils";
import { buildApiUrl } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import {
  DEFAULT_CLIP_DURATION,
  DEFAULT_FILM_LANGUAGE,
  DEFAULT_LIBRARY_TAB,
  DEFAULT_ORIENTATION,
  DEFAULT_PROJECT_TAB,
  DEFAULT_STYLE_ID,
  EMPTY_STORY_BIBLE_LABEL,
  EMPTY_VALUE_LABEL,
  EPISODE_STEP_LABELS,
  EPISODE_STEPS,
  FILM_LANGUAGE_LABELS,
  FILMS_LIBRARY_PATH,
  FILMS_PATH,
  GENERATE_LABEL,
  LANDSCAPE_ENTITY_TYPES,
  LIBRARY_TAB_OPTIONS,
  MEDIA_FAILED_LABEL_PREFIX,
  MEDIA_GENERATING_LABEL,
  MEDIA_QUEUED_LABEL,
  NOT_WRITTEN_PART_LABEL,
  NO_VOICE_VALUE,
  PROJECT_NAME_MAX_LENGTH,
  PROJECT_TAB_OPTIONS,
  REGENERATE_LABEL,
  REWRITABLE_EPISODE_STATUSES,
  SCENE_CLIP_DURATION_LOWER_LIMIT_S,
  SCENE_CLIP_DURATION_UPPER_LIMIT_S,
  TARGET_DURATION_LOWER_LIMIT_S,
  type LibraryTab,
  type ProjectTab,
} from "./constants";
import type {
  CharacterDraft,
  CharacterFields,
  CreateProjectFields,
  EntityType,
  Episode,
  EpisodeDetail,
  EpisodeDownloadFile,
  EpisodePart,
  EpisodePartWithCounts,
  EpisodeStage,
  EpisodeStatus,
  EpisodeStep,
  FilmCharacter,
  FilmLanguage,
  FilmLookSettings,
  FilmProject,
  FilmProjectDetail,
  FilmStyle,
  MediaStatus,
  Orientation,
  PartCounts,
  PartDraft,
  PartFields,
  ProjectSettings,
  ProjectSettingsDraft,
  Scene,
  SceneChanges,
  ScenePromptFields,
  ScenePromptsDraft,
  SelectableOption,
  StageState,
  StyleDraft,
  StyleFields,
  TrimDraft,
  VoiceDraft,
  VoiceTemplate,
} from "./types";

const FILM_FILES_PATH = "/films/files";
const LOADING_OPTION_LABEL = "Loading…";
const FILMS_DIR_MARKER = "/films/";
const ABSOLUTE_PATH_PATTERN = /^(?:\/|[a-z]:\/)/i;
const BUSY_MEDIA_STATUSES: ReadonlySet<MediaStatus> = new Set(["queued", "processing"]);
const MISSING_MEDIA_STATUSES: ReadonlySet<MediaStatus> = new Set(["none", "failed"]);
const PASSED_IMAGE_REQUEST_KINDS: ReadonlySet<GenerationRequest["kind"]> = new Set(["scene_image", "edit_image"]);
const STAGE_STATE_BY_EPISODE_STATUS: Record<EpisodeStatus, StageState> = {
  draft: "upcoming",
  running: "current",
  paused: "paused",
  failed: "failed",
  done: "completed",
};
const UNSAFE_FILE_STEM_CHARACTERS = /[^\p{L}\p{N}_\-. ]+/gu;
const FILE_STEM_TRIMMED_CHARACTERS = /^[ ._]+|[ ._]+$/g;
const FALLBACK_FILE_STEM = "video";
const EXTENSION_SEPARATOR = ".";
const MS_PER_SECOND = 1_000;
const DECIMAL_RADIX = 10;
const STORY_BIBLE_STEP: EpisodeStep = "updating_story_bible";
const SCRIPT_STEP: EpisodeStep = "writing_script";
const PART_REWRITE_HIDDEN_STATUS: EpisodeStatus = "draft";
const NO_PART_COUNTS: PartCounts = {
  sceneCount: 0,
  imagesDone: 0,
  clipsDone: 0,
  narrationDone: 0,
  narrationWithText: 0,
  failedCount: 0,
  openRequestCount: 0,
};

export function buildFilmFileUrl(relativePath: string, version: string): string {
  const encodedPath = relativePath.split("/").map(encodeURIComponent).join("/");
  return buildApiUrl(`${FILM_FILES_PATH}/${encodedPath}?v=${encodeURIComponent(version)}`);
}

export function buildEpisodeDownloadUrl(episodeId: string, file: EpisodeDownloadFile): string {
  return buildApiUrl(`${FILMS_PATH}/episodes/${encodeURIComponent(episodeId)}/download?file=${file}`);
}

export function buildFilmProjectPath(projectId: string): string {
  return `${FILMS_PATH}/${encodeURIComponent(projectId)}`;
}

export function buildFilmProjectTabPath(projectId: string, tab: ProjectTab): string {
  return `${buildFilmProjectPath(projectId)}?tab=${tab}`;
}

export function resolveProjectTab(requestedTab: string | undefined): ProjectTab {
  const matchingOption = PROJECT_TAB_OPTIONS.find((option) => option.value === requestedTab);
  return matchingOption?.value ?? DEFAULT_PROJECT_TAB;
}

export function buildFilmEpisodePath(projectId: string, episodeNumber: number): string {
  return `${buildFilmProjectPath(projectId)}/episodes/${episodeNumber}`;
}

export function buildFilmLibraryPath(tab: LibraryTab): string {
  return `${FILMS_LIBRARY_PATH}?tab=${tab}`;
}

export function resolveLibraryTab(requestedTab: string | undefined): LibraryTab {
  const matchingOption = LIBRARY_TAB_OPTIONS.find((option) => option.value === requestedTab);
  return matchingOption?.value ?? DEFAULT_LIBRARY_TAB;
}

export function parseEpisodeNumber(episodeNumberText: string): number {
  return parseInt(episodeNumberText, DECIMAL_RADIX);
}

export function toFilmsRelativePath(path: string): string | undefined {
  const normalizedPath = path.replaceAll("\\", "/");
  const markerIndex = normalizedPath.lastIndexOf(FILMS_DIR_MARKER);
  if (markerIndex >= 0) return normalizedPath.slice(markerIndex + FILMS_DIR_MARKER.length);
  return ABSOLUTE_PATH_PATTERN.test(normalizedPath) ? undefined : normalizedPath;
}

export function describeDuration(durationMs: number | null): string {
  return durationMs === null ? EMPTY_VALUE_LABEL : formatTimestamp(durationMs);
}

export function isValidTargetDuration(targetDurationS: number): boolean {
  return Number.isInteger(targetDurationS) && targetDurationS >= TARGET_DURATION_LOWER_LIMIT_S;
}

export function findScenePassLabel(sceneId: string, openRequests: readonly GenerationRequest[]): string | undefined {
  const passedRequest = openRequests.find(
    (request) =>
      request.sceneId === sceneId && PASSED_IMAGE_REQUEST_KINDS.has(request.kind) && describePassProgress(request),
  );
  return passedRequest && describePassProgress(passedRequest);
}

export function findSceneSegmentLabel(sceneId: string, openRequests: readonly GenerationRequest[]): string | undefined {
  const segmentedRequest = openRequests.find(
    (request) => request.sceneId === sceneId && request.kind === "scene_clip" && describeSegmentProgress(request),
  );
  return segmentedRequest && describeSegmentProgress(segmentedRequest);
}

export function isValidSceneClipDuration(clipDurationText: string): boolean {
  const clipDurationS = Number(clipDurationText);
  return (
    Number.isInteger(clipDurationS) &&
    clipDurationS >= SCENE_CLIP_DURATION_LOWER_LIMIT_S &&
    clipDurationS <= SCENE_CLIP_DURATION_UPPER_LIMIT_S
  );
}

export function buildEpisodeStages(episode: Pick<EpisodeDetail, "status" | "step" | "parts">): EpisodeStage[] {
  const scriptPartProgress = describeScriptPartProgress(episode);
  return EPISODE_STEPS.map((step) => ({
    step,
    label: EPISODE_STEP_LABELS[step],
    state: determineStageState(episode, step),
    progressLabel: step === SCRIPT_STEP ? scriptPartProgress : undefined,
  }));
}

export function describeEpisodeAiUsed(episode: Pick<Episode, "aiUsed">): string {
  return joinAiUsedDescriptions(listAiUsedDescriptions(episode.aiUsed, EPISODE_STEPS, EPISODE_STEP_LABELS));
}

export function describeEpisodeStep(episode: Pick<Episode, "status" | "step">): string {
  if (episode.status === "done") return COMPLETED_JOB_STEP_LABEL;
  if (episode.step === null) return NOT_STARTED_JOB_STEP_LABEL;
  return EPISODE_STEP_LABELS[episode.step];
}

export function describePausedNotice(step: EpisodeStep): string {
  return `Paused after ${EPISODE_STEP_LABELS[step]} — check the work, then Continue.`;
}

export function describeEpisodeNumber(episodeNumber: number): string {
  return `E${episodeNumber}`;
}

export function describeEpisodeProgress(parts: readonly PartCounts[]): string {
  const { sceneCount, imagesDone, clipsDone, narrationDone, narrationWithText } = parts.reduce(
    addPartCounts,
    NO_PART_COUNTS,
  );
  return `Parts ${parts.length} · Scenes ${sceneCount} · Images ${imagesDone}/${sceneCount} · Clips ${clipsDone}/${sceneCount} · Narration ${narrationDone}/${narrationWithText}`;
}

export function describePartMediaProgress(part: Pick<PartCounts, "sceneCount" | "imagesDone" | "clipsDone">): string {
  return `Images ${part.imagesDone}/${part.sceneCount} · Clips ${part.clipsDone}/${part.sceneCount}`;
}

export function describePartSceneCount(part: Pick<PartCounts, "sceneCount">): string {
  return part.sceneCount > 0 ? describeCount(part.sceneCount, "scenes") : NOT_WRITTEN_PART_LABEL;
}

export function describeScriptPartProgress(episode: Pick<EpisodeDetail, "status" | "step" | "parts">): string | undefined {
  if (episode.status !== "running" || episode.step !== SCRIPT_STEP) return undefined;
  const writingPartIndex = episode.parts.findIndex((part) => part.sceneCount === 0);
  if (writingPartIndex < 0) return undefined;
  return `Part ${writingPartIndex + 1} of ${episode.parts.length}`;
}

export function canRewriteScript(episode: Pick<EpisodeDetail, "status" | "parts">): boolean {
  return REWRITABLE_EPISODE_STATUSES.has(episode.status) && !episode.parts.some(hasPartMedia);
}

export function isPartRewriteShown(
  episode: Pick<Episode, "status">,
  part: Pick<PartCounts, "imagesDone" | "clipsDone">,
): boolean {
  return episode.status !== PART_REWRITE_HIDDEN_STATUS && !hasPartMedia(part);
}

export function toPartNumber(part: Pick<EpisodePart, "position">): number {
  return part.position + 1;
}

export function countScenesBeforePart(parts: readonly EpisodePartWithCounts[], partPosition: number): number {
  return parts
    .filter((part) => part.position < partPosition)
    .reduce((sceneTotal, part) => sceneTotal + part.sceneCount, 0);
}

export function findStoryBibleEpisode<TEpisode extends Pick<Episode, "status" | "step">>(
  episodes: readonly TEpisode[],
): TEpisode | undefined {
  return episodes.find((episode) => episode.status === "running" && episode.step === STORY_BIBLE_STEP);
}

export function describeStoryBibleUpdate(
  project: Pick<FilmProject, "storyBibleEpisodeId" | "storyBibleUpdatedAt">,
  episodes: readonly Pick<Episode, "id" | "number">[],
): string {
  const { storyBibleEpisodeId, storyBibleUpdatedAt } = project;
  if (storyBibleUpdatedAt === null) return EMPTY_STORY_BIBLE_LABEL;
  const updatedTime = formatDateTime(storyBibleUpdatedAt);
  if (storyBibleEpisodeId === null) return `Edited by you · ${updatedTime}`;
  const writingEpisode = episodes.find((episode) => episode.id === storyBibleEpisodeId);
  if (!writingEpisode) return `Updated · ${updatedTime}`;
  return `Updated by ${describeEpisodeNumber(writingEpisode.number)} · ${updatedTime}`;
}

export function describeStoryBibleUpdatingHint(episodeNumber: number): string {
  return `${describeEpisodeNumber(episodeNumber)} is updating the story bible.`;
}

export function isMediaBusy(status: MediaStatus): boolean {
  return BUSY_MEDIA_STATUSES.has(status);
}

export function isFilmEpisodeBusy(episode: Pick<EpisodeDetail, "status" | "openRequests" | "parts">): boolean {
  return (
    episode.status === "running" ||
    episode.openRequests.length > 0 ||
    episode.parts.some((part) => part.openRequestCount > 0)
  );
}

export function isFilmProjectBusy(project: Pick<FilmProjectDetail, "episodes" | "characters">): boolean {
  const hasRunningEpisode = project.episodes.some((episode) => episode.status === "running");
  return hasRunningEpisode || project.characters.some((character) => isMediaBusy(character.referenceStatus));
}

export function findQueuedRequest(
  openRequests: readonly GenerationRequest[],
  isMatch: (request: GenerationRequest) => boolean,
): GenerationRequest | undefined {
  return openRequests.find((request) => request.status === "queued" && isMatch(request));
}

export function isSceneBusy(scene: Scene, openRequests: readonly GenerationRequest[]): boolean {
  const hasBusyPart = [scene.imageStatus, scene.clipStatus, scene.narrationStatus].some(isMediaBusy);
  return hasBusyPart || openRequests.some((request) => request.sceneId === scene.id);
}

export function describeMediaProgress(status: MediaStatus, error: string | null): string | undefined {
  if (status === "queued") return MEDIA_QUEUED_LABEL;
  if (status === "processing") return MEDIA_GENERATING_LABEL;
  if (status === "failed") return `${MEDIA_FAILED_LABEL_PREFIX}${error ?? EMPTY_VALUE_LABEL}`;
  return undefined;
}

export function describeBusyMedia(status: MediaStatus): string | undefined {
  return isMediaBusy(status) ? describeMediaProgress(status, null) : undefined;
}

export function findSettledMediaError(status: MediaStatus, error: string | null): string | null {
  return isMediaBusy(status) ? null : error;
}

export function describeGenerateLabel(status: MediaStatus): string {
  return status === "done" ? REGENERATE_LABEL : GENERATE_LABEL;
}

export function countMissingReferences(characters: readonly Pick<FilmCharacter, "referenceStatus">[]): number {
  return characters.filter((character) => isMediaMissing(character.referenceStatus)).length;
}

export function entityTypeToOrientation(entityType: EntityType): Orientation {
  return LANDSCAPE_ENTITY_TYPES.has(entityType) ? "landscape" : "portrait";
}

export function buildDeleteProjectConfirmation(projectName: string): string {
  return `Delete project '${projectName}'? Its episodes and their files are removed; characters stay in the library.`;
}

export function buildDeleteEpisodeConfirmation(episodeNumber: number): string {
  return `Delete episode ${episodeNumber}? Its scenes and files are removed.`;
}

export function buildDeleteSceneConfirmation(sceneNumber: number): string {
  return `Delete scene ${sceneNumber}?`;
}

export function buildDeletePartConfirmation(partNumber: number): string {
  return `Delete part ${partNumber}?`;
}

export function buildRewritePartConfirmation(partNumber: number): string {
  return `Rewrite part ${partNumber}? Its scenes are deleted and written again.`;
}

export function buildDeleteCharacterConfirmation(characterName: string): string {
  return `Delete character '${characterName}'?`;
}

export function buildDeleteStyleConfirmation(styleName: string): string {
  return `Delete style '${styleName}'?`;
}

export function buildDeleteVoiceConfirmation(voiceName: string): string {
  return `Delete voice '${voiceName}'?`;
}

export function toSceneNumber(scene: Pick<Scene, "position">, scenesBeforePart: number): number {
  return scenesBeforePart + scene.position + 1;
}

export function describeCount(count: number, noun: string): string {
  return `${count} ${noun}`;
}

export function chooseFilmLanguage(candidateLanguages: readonly string[]): FilmLanguage {
  return candidateLanguages.find(isFilmLanguage) ?? DEFAULT_FILM_LANGUAGE;
}

export function buildProjectNameFromFilename(sourceFilename: string): string {
  return toSafeFileStem(sourceFilename).slice(0, PROJECT_NAME_MAX_LENGTH);
}

export function buildProjectNameFromScriptTitle(scriptTitle: string | null): string {
  return (scriptTitle ?? "").slice(0, PROJECT_NAME_MAX_LENGTH);
}

export function toFilmLanguage(language: string | null): FilmLanguage | null {
  return language !== null && isFilmLanguage(language) ? language : null;
}

export function hasNarratorWhenNarrating(draft: Pick<ProjectSettingsDraft, "allowNarration" | "narratorVoiceId">): boolean {
  return !draft.allowNarration || draft.narratorVoiceId !== NO_VOICE_VALUE;
}

export function createDefaultLookSettings(language: FilmLanguage): FilmLookSettings {
  return {
    language,
    orientation: DEFAULT_ORIENTATION,
    styleId: DEFAULT_STYLE_ID,
  };
}

export function createDefaultProjectDraft(language: FilmLanguage): ProjectSettingsDraft {
  return {
    ...createDefaultLookSettings(language),
    name: "",
    description: "",
    clipDurationS: DEFAULT_CLIP_DURATION,
    allowDialogue: true,
    allowNarration: true,
    narratorVoiceId: NO_VOICE_VALUE,
    allowMusic: false,
  };
}

export function buildAnalysisProjectFields(projectName: string, lookSettings: FilmLookSettings): CreateProjectFields {
  const projectDraft = { ...createDefaultProjectDraft(lookSettings.language), ...lookSettings, name: projectName };
  return {
    ...settingsDraftToFields(projectDraft),
    allowNarration: false,
    characterIds: [],
  };
}

export function projectToSettingsDraft(project: FilmProject): ProjectSettingsDraft {
  return {
    name: project.name,
    description: project.description ?? "",
    language: project.language,
    orientation: project.orientation,
    styleId: project.styleId,
    clipDurationS: String(project.clipDurationS),
    allowDialogue: project.allowDialogue,
    allowNarration: project.allowNarration,
    narratorVoiceId: project.narratorVoiceId ?? NO_VOICE_VALUE,
    allowMusic: project.allowMusic,
  };
}

export function settingsDraftToFields(draft: ProjectSettingsDraft): ProjectSettings {
  return {
    ...draft,
    name: draft.name.trim(),
    description: blankToNull(draft.description),
    clipDurationS: parseInt(draft.clipDurationS, DECIMAL_RADIX),
    narratorVoiceId: draft.narratorVoiceId === NO_VOICE_VALUE ? null : draft.narratorVoiceId,
  };
}

export function createEmptyCharacterDraft(): CharacterDraft {
  return {
    name: "",
    entityType: "character",
    description: "",
    imagePrompt: "",
    voiceDescription: "",
    styleId: DEFAULT_STYLE_ID,
  };
}

export function characterToDraft(character: FilmCharacter): CharacterDraft {
  return {
    name: character.name,
    entityType: character.entityType,
    description: character.description,
    imagePrompt: character.imagePrompt,
    voiceDescription: character.voiceDescription ?? "",
    styleId: character.styleId,
  };
}

export function characterDraftToFields(draft: CharacterDraft): CharacterFields {
  return {
    name: draft.name.trim(),
    entityType: draft.entityType,
    description: draft.description,
    imagePrompt: blankToNull(draft.imagePrompt),
    voiceDescription: blankToNull(draft.voiceDescription),
    styleId: draft.styleId,
  };
}

export function createEmptyStyleDraft(): StyleDraft {
  return { name: "", styleInstruction: "", negativePrompt: "", scenePrefix: "", lighting: "" };
}

export function styleToDraft(style: FilmStyle): StyleDraft {
  return {
    name: style.name,
    styleInstruction: style.styleInstruction,
    negativePrompt: style.negativePrompt ?? "",
    scenePrefix: style.scenePrefix ?? "",
    lighting: style.lighting,
  };
}

export function styleDraftToFields(draft: StyleDraft): StyleFields {
  return {
    name: draft.name.trim(),
    styleInstruction: draft.styleInstruction,
    negativePrompt: blankToNull(draft.negativePrompt),
    scenePrefix: blankToNull(draft.scenePrefix),
    lighting: blankToNull(draft.lighting),
  };
}

export function createEmptyVoiceDraft(): VoiceDraft {
  return { name: "", description: "", sampleText: "" };
}

export function voiceToDraft(voice: VoiceTemplate): VoiceDraft {
  return { name: voice.name, description: voice.description ?? "", sampleText: voice.sampleText };
}

export function sceneToPromptsDraft(scene: Scene): ScenePromptsDraft {
  return {
    imagePrompt: scene.imagePrompt,
    videoPrompt: scene.videoPrompt,
    narratorText: scene.narratorText ?? "",
    clipDurationS: String(scene.clipDurationS),
    characterIds: scene.characterIds,
  };
}

export function createEmptyScenePromptsDraft(defaultClipDurationS: number): ScenePromptsDraft {
  return {
    imagePrompt: "",
    videoPrompt: "",
    narratorText: "",
    clipDurationS: String(defaultClipDurationS),
    characterIds: [],
  };
}

export function createEmptyPartDraft(): PartDraft {
  return { title: "", plan: "", targetDurationText: "" };
}

export function partToDraft(part: Pick<EpisodePart, "title" | "plan" | "targetDurationS">): PartDraft {
  return { title: part.title, plan: part.plan, targetDurationText: String(part.targetDurationS) };
}

export function partDraftToFields(draft: PartDraft): PartFields {
  return { title: draft.title, plan: draft.plan, targetDurationS: Number(draft.targetDurationText) };
}

export function promptsDraftToFields(draft: ScenePromptsDraft): ScenePromptFields {
  return {
    ...draft,
    narratorText: blankToNull(draft.narratorText),
    clipDurationS: parseInt(draft.clipDurationS, DECIMAL_RADIX),
  };
}

export function buildScenePromptChanges(draft: ScenePromptsDraft, savedDraft: ScenePromptsDraft): SceneChanges {
  const { characterIds, ...textFields } = promptsDraftToFields(draft);
  const { characterIds: savedCharacterIds, ...savedTextFields } = promptsDraftToFields(savedDraft);
  const textChanges = pickChangedFields(textFields, savedTextFields);
  return characterIds.join() === savedCharacterIds.join() ? textChanges : { ...textChanges, characterIds };
}

export function stylesToOptions(styles: readonly FilmStyle[] | undefined, selectedStyleId: string): SelectableOption[] {
  if (!styles) return [{ value: selectedStyleId, label: LOADING_OPTION_LABEL }];
  return styles.map((style) => ({ value: style.id, label: style.name }));
}

export function voicesToOptions(voices: readonly VoiceTemplate[] | undefined): SelectableOption[] {
  const voiceOptions = (voices ?? []).map((voice) => ({ value: voice.id, label: voice.name }));
  return [{ value: NO_VOICE_VALUE, label: EMPTY_VALUE_LABEL }, ...voiceOptions];
}

export function charactersToOptions(characters: readonly Pick<FilmCharacter, "id" | "name">[]): SelectableOption[] {
  return characters.map((character) => ({ value: character.id, label: character.name }));
}

export function doneAnalysesToOptions(jobs: readonly Job[]): SelectableOption[] {
  return jobs
    .filter((job) => job.status === "done")
    .map((job) => ({ value: job.id, label: `${job.sourceFilename} · ${formatDateTime(job.createdAt)}` }));
}

export function haveSameScenePrompts(first: ScenePromptsDraft, second: ScenePromptsDraft): boolean {
  return !hasChangedFields(buildScenePromptChanges(first, second));
}

export function pickChangedFields<TFields extends object>(nextFields: TFields, currentFields: TFields): Partial<TFields> {
  const changedEntries = Object.entries(nextFields).filter(
    ([field, value]) => currentFields[field as keyof TFields] !== value,
  );
  return Object.fromEntries(changedEntries) as Partial<TFields>;
}

export function hasChangedFields(changes: object): boolean {
  return Object.keys(changes).length > 0;
}

export function buildEpisodeSourcePath(
  episode: Pick<EpisodeDetail, "source" | "sourceJobId" | "sourceCloneId" | "isSourceDeleted">,
): string | undefined {
  if (episode.isSourceDeleted) return undefined;
  if (episode.source === "film_analysis" && episode.sourceJobId) return buildFilmAnalysisDetailPath(episode.sourceJobId);
  if (episode.source === "film_clone" && episode.sourceCloneId) return buildFilmCloneDetailPath(episode.sourceCloneId);
  return undefined;
}

export function sceneToTrimDraft(scene: Pick<Scene, "trimStartMs" | "trimEndMs" | "clipDurationMs">): TrimDraft {
  return {
    startSecondsText: msToSecondsText(scene.trimStartMs),
    endSecondsText: msToSecondsText(scene.trimEndMs ?? scene.clipDurationMs ?? 0),
  };
}

export function secondsTextToMs(secondsText: string): number | undefined {
  const seconds = parseFloat(secondsText);
  return Number.isFinite(seconds) ? Math.round(seconds * MS_PER_SECOND) : undefined;
}

export function sortByName<TItem extends { name: string }>(items: readonly TItem[]): TItem[] {
  return [...items].sort((first, second) => first.name.localeCompare(second.name));
}

function isFilmLanguage(language: string): language is FilmLanguage {
  return Object.hasOwn(FILM_LANGUAGE_LABELS, language);
}

function toSafeFileStem(sourceFilename: string): string {
  const stem = removeExtension(sourceFilename)
    .replace(UNSAFE_FILE_STEM_CHARACTERS, "_")
    .replace(FILE_STEM_TRIMMED_CHARACTERS, "");
  return stem || FALLBACK_FILE_STEM;
}

function removeExtension(fileName: string): string {
  const separatorIndex = fileName.lastIndexOf(EXTENSION_SEPARATOR);
  const hasExtension = separatorIndex > 0 && separatorIndex < fileName.length - 1;
  return hasExtension ? fileName.slice(0, separatorIndex) : fileName;
}

function blankToNull(text: string): string | null {
  return text.trim() ? text : null;
}

function describePassProgress(request: GenerationRequest): string | undefined {
  const { pass, passes } = request.params;
  if (typeof pass !== "number" || typeof passes !== "number") return undefined;
  return `Pass ${pass} of ${passes}`;
}

function describeSegmentProgress(request: GenerationRequest): string | undefined {
  const { segment, segments } = request.params;
  if (typeof segment !== "number" || typeof segments !== "number") return undefined;
  return `Part ${segment} of ${segments}`;
}

function determineStageState(episode: Pick<Episode, "status" | "step">, step: EpisodeStep): StageState {
  if (episode.status === "done") return "completed";
  if (episode.step === null) return "upcoming";
  const stepIndex = EPISODE_STEPS.indexOf(step);
  const currentStepIndex = EPISODE_STEPS.indexOf(episode.step);
  if (stepIndex < currentStepIndex) return "completed";
  if (stepIndex > currentStepIndex) return "upcoming";
  return STAGE_STATE_BY_EPISODE_STATUS[episode.status];
}

function hasPartMedia(part: Pick<PartCounts, "imagesDone" | "clipsDone">): boolean {
  return part.imagesDone > 0 || part.clipsDone > 0;
}

function addPartCounts(total: PartCounts, part: PartCounts): PartCounts {
  return {
    sceneCount: total.sceneCount + part.sceneCount,
    imagesDone: total.imagesDone + part.imagesDone,
    clipsDone: total.clipsDone + part.clipsDone,
    narrationDone: total.narrationDone + part.narrationDone,
    narrationWithText: total.narrationWithText + part.narrationWithText,
    failedCount: total.failedCount + part.failedCount,
    openRequestCount: total.openRequestCount + part.openRequestCount,
  };
}

function isMediaMissing(status: MediaStatus): boolean {
  return MISSING_MEDIA_STATUSES.has(status);
}

function msToSecondsText(durationMs: number): string {
  return String(durationMs / MS_PER_SECOND);
}
