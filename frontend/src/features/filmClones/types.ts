import type { Job, JobOptions, JobStep } from "@/features/jobs/types";
import type { PresetPrompts, PresetSnapshot } from "@/features/promptPresets/types";
import type { AiProviderId, AiUsed, InputMode } from "@/features/settings/types";

export type FilmCloneStatus = "running" | "waiting" | "done" | "failed";

export type FilmCloneStep =
  | "analyzing"
  | "extracting_assets"
  | "analyzing_shots"
  | "choosing_localization"
  | "proposing"
  | "reviewing"
  | "writing_script"
  | "generating_scene_images";

export type FilmCloneJobType = "film_clone" | "youtube_film_clone";

export type CloneJobStep = Extract<
  JobStep,
  | "extracting_audio"
  | "transcribing"
  | "fetching_transcript"
  | "listening_to_audio"
  | "picking_moments"
  | "downloading_video"
  | "sampling_frames"
  | "detecting_scenes"
  | "capturing_frames"
  | "writing_markdown"
>;

export type CloneStageState = "completed" | "current" | "waiting" | "failed" | "upcoming";

export interface CloneStage {
  label: string;
  state: CloneStageState;
}

export type CloneSourceKind = "upload" | "youtube";

export type CloneAspect = "16:9" | "9:16";

export type CloneImageOrientation = "landscape" | "portrait";

export type AssetKind = "character" | "costume" | "prop" | "location";

export type FrameKind = "dialogue" | "sound" | "scene";

export type ShotSize =
  | "extreme_wide"
  | "wide"
  | "full"
  | "medium"
  | "medium_close"
  | "close_up"
  | "extreme_close_up";

export type CameraAngle =
  | "eye_level"
  | "high"
  | "low"
  | "birds_eye"
  | "worms_eye"
  | "dutch"
  | "over_the_shoulder"
  | "pov";

export type CloneImageStatus = "none" | "queued" | "processing" | "done" | "failed";

export type TargetCountryCode = "vn" | "jp" | "kr" | "cn" | "us" | "gb" | "fr" | "th" | "in" | "id";

export type ScriptLanguageCode = "vi" | "ja" | "ko" | "zh" | "en" | "fr" | "th" | "hi" | "id";

export type GenerationKind =
  | "character_image"
  | "scene_image"
  | "edit_image"
  | "scene_clip"
  | "narration"
  | "music"
  | "thumbnail"
  | "clone_reference_image"
  | "clone_scene_image";

export type GenerationStatus = "queued" | "processing" | "done" | "failed" | "cancelled";

export type MediaKind = "image" | "edit_image" | "video" | "speech" | "music";

export interface FilmClone {
  id: string;
  jobId: string;
  status: FilmCloneStatus;
  step: FilmCloneStep;
  errorMessage: string | null;
  targetCountry: TargetCountryCode | null;
  targetSetting: string | null;
  changeAppearance: boolean;
  changeCostume: boolean;
  changeSetting: boolean;
  shouldRunAutomatically: boolean;
  scriptLanguage: string | null;
  aspect: CloneAspect | null;
  scriptTitle: string | null;
  logline: string | null;
  preset: PresetSnapshot;
  prompts: Partial<PresetPrompts>;
  aiUsed: AiUsed<FilmCloneStep>;
  createdAt: string;
  updatedAt: string;
  finishedAt: string | null;
  sourceFilename: string;
  sourceKind: CloneSourceKind;
  jobStep: CloneJobStep | null;
  hasOpenRequests: boolean;
}

export interface CloneAsset {
  id: string;
  cloneId: string;
  position: number;
  kind: AssetKind;
  name: string;
  description: string;
  culture: string;
  period: string;
  frames: string[];
  referenceFrame: string | null;
  changed: boolean;
  localizedName: string | null;
  localizedDescription: string | null;
  localizationNote: string | null;
  referenceStatus: CloneImageStatus;
  referencePath: string | null;
  referenceError: string | null;
}

export interface CloneShot {
  id: string;
  position: number;
  atMs: number;
  frame: string;
  frameKind: FrameKind;
  shotSize: ShotSize | null;
  cameraAngle: CameraAngle | null;
  emotion: string | null;
  action: string | null;
  assetIds: string[];
}

export interface CloneScene {
  id: string;
  cloneId: string;
  shotId: string;
  position: number;
  description: string;
  dialogue: string | null;
  imagePrompt: string;
  assetIds: string[];
  imageStatus: CloneImageStatus;
  imagePath: string | null;
  imageError: string | null;
}

export interface GenerationRequest {
  id: string;
  kind: GenerationKind;
  mediaKind: MediaKind;
  projectId: string | null;
  cloneId: string | null;
  episodeId: string | null;
  sceneId: string | null;
  characterId: string | null;
  cloneAssetId: string | null;
  cloneSceneId: string | null;
  provider: string;
  status: GenerationStatus;
  params: Record<string, unknown>;
  attempts: number;
  nextAttemptAt: string | null;
  errorMessage: string | null;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
}

export type CloneJobOptions = Omit<JobOptions, "inputMode"> & {
  inputMode?: InputMode;
};

export type CloneJob = Omit<Job, "type" | "step" | "options"> & {
  type: FilmCloneJobType;
  step: CloneJobStep | null;
  options: CloneJobOptions;
};

export interface FilmCloneDetail extends FilmClone {
  job: CloneJob | null;
  videoNotes: string | null;
  assets: CloneAsset[];
  shots: CloneShot[];
  scenes: CloneScene[];
  generationRequests: GenerationRequest[];
  aiActivity: AiActivity | null;
}

export interface AiActivity {
  provider: AiProviderId;
  model: string;
  label: string;
  startedAt: string;
  lastOutputAt: string | null;
}

export interface LocalizationChoices {
  targetCountry: TargetCountryCode | null;
  targetSetting: string;
  changeAppearance: boolean;
  changeCostume: boolean;
  changeSetting: boolean;
}

export type LocalizationFlagKey = "changeAppearance" | "changeCostume" | "changeSetting";

export type LocalizationFlags = Pick<LocalizationChoices, LocalizationFlagKey>;

export interface AutomaticRunChoices {
  shouldRunAutomatically: boolean;
  choices: LocalizationChoices;
}

export interface OriginalAssetChanges {
  name: string;
  kind: AssetKind;
  description: string;
  culture: string;
  period: string;
}

export interface LocalizedAssetDraft {
  localizedName: string;
  localizedDescription: string;
}

export interface LocalizedAssetChanges {
  changed?: boolean;
  localizedName?: string;
  localizedDescription?: string;
}

export interface SceneChanges {
  description: string;
  dialogue: string;
  imagePrompt: string;
}
