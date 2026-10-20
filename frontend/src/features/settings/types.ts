import type {
  ImageRouteProviderId,
  ModelIdsByProvider,
  ProviderId,
  ProviderRoutes,
  ProviderSettings,
  VideoRouteProviderId,
} from "@/features/providers/types";

export type ScriptLanguage = "follow_target_country" | "vi" | "ja" | "ko" | "zh" | "en" | "fr" | "th" | "hi" | "id";

export type AiProviderId = Extract<ProviderId, "claude_cli" | "google" | "openai">;

export type AiStepGroup = "moments" | "audio" | "filmAnalysis" | "filmScript" | "filmClone";

export type InputMode = "subtitles" | "whole_video";

export type FilmAnalysisInputMode = InputMode | "full_video";

export interface AiModel {
  provider: AiProviderId;
  model: string;
}

export type AiStepModels = Record<AiStepGroup, AiModel | null>;

export interface AppSettings {
  scriptLanguage: ScriptLanguage;
  aiModel: AiModel;
  aiStepModels: AiStepModels;
  inputMode: InputMode;
  filmAnalysisInputMode: FilmAnalysisInputMode;
  filmCloneInputMode: InputMode;
  filmCloneImageProvider: ImageRouteProviderId | null;
  filmStudioImageProvider: ImageRouteProviderId | null;
  filmStudioClipProvider: VideoRouteProviderId | null;
}

export type MediaProviderSettingKey = "filmCloneImageProvider" | "filmStudioImageProvider" | "filmStudioClipProvider";

export type AiModelSettings = Pick<AppSettings, "aiModel" | "aiStepModels" | "inputMode" | "filmAnalysisInputMode">;

export interface AiModelsDraft {
  settings: Partial<AiModelSettings>;
  routes: Partial<ProviderRoutes>;
  modelIdsByProvider: ModelIdsByProvider;
}

export interface AiModelsUpdate extends Partial<AiModelSettings> {
  routes?: Partial<ProviderRoutes>;
  models?: ModelIdsByProvider;
}

export interface AiModelsSaveResult {
  settings: AppSettings;
  providers: ProviderSettings;
}

export interface AiUsedEntry extends AiModel {
  label: string;
}

export type AiUsed<TStep extends string> = Partial<Record<TStep, AiUsedEntry>>;

export interface ResolvedAiModel {
  label: string;
  providerName: string;
  isSetUp: boolean;
}

export interface AiGroupModel extends ResolvedAiModel {
  group: AiStepGroup;
  aiModel: AiModel;
  needsGoogleAi: boolean;
}

export type AiRun =
  | { kind: "videoToMarkdown" | "filmAnalysis" | "filmClone" | "filmScript" }
  | { kind: "filmAnalysisRerun"; sourceInputMode: FilmAnalysisInputMode | undefined };

export interface AiRunPlan {
  groups: readonly AiStepGroup[];
  inputMode?: FilmAnalysisInputMode;
  inputModeLabel?: string;
}

export interface AiModelStatus extends Omit<AiRunPlan, "groups"> {
  groupModels: AiGroupModel[];
}

export interface AiModelOption {
  value: string;
  label: string;
  group: string;
  aiModel: AiModel;
}

export interface ResolvedMediaProvider {
  id: ProviderId;
  name: string;
  isSetUp: boolean;
}

export type MediaProviderStatus = Record<MediaProviderSettingKey, ResolvedMediaProvider>;
