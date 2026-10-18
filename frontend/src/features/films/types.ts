import type { GenerationRequest, GenerationStatus } from "@/features/filmClones/types";
import type { PresetSnapshot } from "@/features/promptPresets/types";
import type { AiUsed } from "@/features/settings/types";

export type FilmLanguage = "vi" | "en" | "ja";

export type Orientation = "landscape" | "portrait";

export type ProjectStatus = "active" | "archived";

export type EntityType = "character" | "location" | "creature" | "visual_asset" | "generic_troop" | "faction";

export type MediaStatus = "none" | "queued" | "processing" | "done" | "failed";

export type ReferenceSource = "generated" | "edited" | "uploaded" | "film_analysis" | "film_clone";

export type SceneImageSource = "generated" | "edited" | "uploaded" | "film_clone";

export type EpisodeSource = "idea" | "film_analysis" | "film_clone";

export type EpisodeStatus = "draft" | "running" | "paused" | "done" | "failed";

export type EpisodeStep =
  | "writing_script"
  | "generating_references"
  | "generating_scene_images"
  | "generating_clips"
  | "generating_audio"
  | "assembling";

export type SubtitleStyle = "clean_white" | "cinematic_gold" | "cyber_amber" | "emerald_hud";

export type EpisodeAction = "start" | "continue" | "stop" | "resume" | "rewrite-script" | "assemble";

export type SceneGenerationAction = "generate-image" | "generate-clip" | "generate-narration";

export type EpisodeDownloadFile = "video" | "subtitles" | "thumbnail";

export type StageState = "completed" | "current" | "paused" | "failed" | "upcoming";

export interface EpisodeStage {
  step: EpisodeStep;
  label: string;
  state: StageState;
}

export interface SelectableOption {
  value: string;
  label: string;
}

export interface StopPoints {
  afterScript: boolean;
  afterReferences: boolean;
  afterSceneImages: boolean;
}

export interface FilmStyle {
  id: string;
  name: string;
  isBuiltin: boolean;
  styleInstruction: string;
  negativePrompt: string | null;
  scenePrefix: string | null;
  lighting: string;
}

export interface VoiceTemplate {
  id: string;
  name: string;
  description: string | null;
  samplePath: string;
  sampleText: string;
  sampleDurationMs: number;
  consentPath: string | null;
  providerVoices: Record<string, string>;
  createdAt: string;
  updatedAt: string;
}

export interface FilmCharacter {
  id: string;
  name: string;
  entityType: EntityType;
  description: string;
  imagePrompt: string;
  voiceDescription: string | null;
  styleId: string;
  styleName: string;
  referenceStatus: MediaStatus;
  referenceSource: ReferenceSource | null;
  referencePath: string | null;
  referenceError: string | null;
  originJobId: string | null;
  originCloneId: string | null;
  providerMedia: Record<string, unknown> | null;
  projectCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface ProjectLink {
  id: string;
  name: string;
}

export interface FilmCharacterDetail extends FilmCharacter {
  projects: ProjectLink[];
}

export interface FilmProject {
  id: string;
  name: string;
  description: string | null;
  language: FilmLanguage;
  orientation: Orientation;
  styleId: string;
  styleName: string;
  clipDurationS: number;
  allowDialogue: boolean;
  allowNarration: boolean;
  narratorVoiceId: string | null;
  allowMusic: boolean;
  status: ProjectStatus;
  lastEpisodeNumber: number;
  flowProjectId: string | null;
  episodeCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface Episode {
  id: string;
  projectId: string;
  number: number;
  title: string;
  logline: string | null;
  source: EpisodeSource;
  idea: string | null;
  sourceJobId: string | null;
  sourceCloneId: string | null;
  targetDurationS: number;
  stopPoints: StopPoints;
  pausedStopPoint: EpisodeStep | null;
  burnSubtitles: boolean;
  subtitleStyle: SubtitleStyle;
  musicPrompt: string | null;
  thumbnailPrompt: string | null;
  musicStatus: MediaStatus;
  musicPath: string | null;
  musicError: string | null;
  preset: PresetSnapshot;
  aiUsed: AiUsed<EpisodeStep>;
  status: EpisodeStatus;
  step: EpisodeStep | null;
  errorMessage: string | null;
  needsAssembly: boolean;
  videoPath: string | null;
  subtitlesPath: string | null;
  thumbnailPath: string | null;
  durationMs: number | null;
  createdAt: string;
  updatedAt: string;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface FilmProjectDetail extends FilmProject {
  characters: FilmCharacter[];
  episodes: Episode[];
  isLookFixed: boolean;
  openRequests: GenerationRequest[];
}

export interface Scene {
  id: string;
  episodeId: string;
  position: number;
  imagePrompt: string;
  videoPrompt: string;
  narratorText: string | null;
  characterIds: string[];
  clipDurationS: number;
  imageStatus: MediaStatus;
  clipStatus: MediaStatus;
  narrationStatus: MediaStatus;
  imageSource: SceneImageSource | null;
  imagePath: string | null;
  clipPath: string | null;
  narrationPath: string | null;
  imageError: string | null;
  clipError: string | null;
  narrationError: string | null;
  clipDurationMs: number | null;
  narrationDurationMs: number | null;
  trimStartMs: number;
  trimEndMs: number | null;
  createdAt: string;
  updatedAt: string;
}

export interface ThumbnailCandidate {
  candidate: number;
  status: GenerationStatus;
  path: string | null;
  errorMessage: string | null;
}

export interface EpisodeDetail extends Episode {
  filmScriptPrompt: string;
  projectName: string;
  isSourceDeleted: boolean;
  scenes: Scene[];
  openRequests: GenerationRequest[];
  thumbnailCandidates: ThumbnailCandidate[];
}

export interface FilmLookSettings {
  language: FilmLanguage;
  orientation: Orientation;
  styleId: string;
}

export interface ProjectSettings extends FilmLookSettings {
  name: string;
  description: string | null;
  clipDurationS: number;
  allowDialogue: boolean;
  allowNarration: boolean;
  narratorVoiceId: string | null;
  allowMusic: boolean;
}

export interface CreateProjectFields extends ProjectSettings {
  characterIds: string[];
}

export type ProjectChanges = Partial<ProjectSettings>;

export interface ProjectSettingsDraft extends FilmLookSettings {
  name: string;
  description: string;
  clipDurationS: string;
  allowDialogue: boolean;
  allowNarration: boolean;
  narratorVoiceId: string;
  allowMusic: boolean;
}

export interface CharacterFields {
  name: string;
  entityType: EntityType;
  description: string;
  imagePrompt: string | null;
  voiceDescription: string | null;
  styleId: string;
}

export interface CharacterDraft {
  name: string;
  entityType: EntityType;
  description: string;
  imagePrompt: string;
  voiceDescription: string;
  styleId: string;
}

export interface StyleFields {
  name: string;
  styleInstruction: string;
  negativePrompt: string | null;
  scenePrefix: string | null;
  lighting: string | null;
}

export interface StyleDraft {
  name: string;
  styleInstruction: string;
  negativePrompt: string;
  scenePrefix: string;
  lighting: string;
}

export interface VoiceDraft {
  name: string;
  description: string;
  sampleText: string;
}

export interface VoiceChanges {
  name?: string;
  description?: string;
  sampleText?: string;
}

export interface CreateEpisodeFields {
  source: EpisodeSource;
  idea?: string;
  sourceJobId?: string;
  sourceCloneId?: string;
  targetDurationS?: number;
  stopPoints?: StopPoints;
  burnSubtitles?: boolean;
  subtitleStyle?: SubtitleStyle;
  presetId?: string;
}

export interface EpisodeChanges {
  title?: string;
  stopPoints?: StopPoints;
  burnSubtitles?: boolean;
  subtitleStyle?: SubtitleStyle;
  musicPrompt?: string;
  thumbnailPrompt?: string;
}

export interface ScenePromptsDraft {
  imagePrompt: string;
  videoPrompt: string;
  narratorText: string;
  clipDurationS: string;
  characterIds: string[];
}

export interface ScenePromptFields {
  imagePrompt: string;
  videoPrompt: string;
  narratorText: string | null;
  clipDurationS: number;
  characterIds: string[];
}

export interface SceneChanges extends Partial<ScenePromptFields> {
  position?: number;
  trimStartMs?: number;
  trimEndMs?: number;
}

export interface TrimDraft {
  startSecondsText: string;
  endSecondsText: string;
}

export interface SceneProgressCounts {
  sceneCount: number;
  doneImageCount: number;
  doneClipCount: number;
  doneNarrationCount: number;
  narrationTextCount: number;
}
