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

export type AiStepGroup = "moments" | "filmAnalysis" | "filmScript" | "filmClone";

export type InputMode = "subtitles" | "whole_video";

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
  filmCloneInputMode: InputMode;
  filmCloneImageProvider: ImageRouteProviderId | null;
  filmStudioImageProvider: ImageRouteProviderId | null;
  filmStudioClipProvider: VideoRouteProviderId | null;
}

export type MediaProviderSettingKey = "filmCloneImageProvider" | "filmStudioImageProvider" | "filmStudioClipProvider";

export type AiModelSettings = Pick<AppSettings, "aiModel" | "aiStepModels" | "inputMode">;

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
}

export interface AiModelStatus {
  groupModels: AiGroupModel[];
  inputMode: InputMode;
  filmCloneInputMode: InputMode;
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
