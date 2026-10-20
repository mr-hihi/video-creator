import { ANALYSIS_MEDIA_KIND, PROVIDER_SHORT_NAMES } from "@/features/providers/constants";
import type { Provider, ProviderId, ProviderRoutes, ProviderSettings, RouteName } from "@/features/providers/types";
import {
  buildRouteOptions,
  pickChangedModelsByProvider,
  pickChangedRoutes,
  type SelectableOption,
} from "@/features/providers/utils";
import {
  AI_MODEL_LIST_SEPARATOR,
  AI_MODEL_OPTION_VALUE_SEPARATOR,
  AI_PROVIDER_IDS,
  AI_STEP_GROUP_LABELS,
  AI_STEP_GROUPS,
  AI_STEP_GROUPS_BY_RUN,
  DEFAULT_INPUT_MODE,
  DEFAULT_SETTINGS_TAB,
  EMPTY_AI_USED_LABEL,
  EMPTY_INPUT_MODE_LABEL,
  FILM_ANALYSIS_AI_STEP_GROUPS_BY_INPUT_MODE,
  FILM_ANALYSIS_INPUT_MODE_LABELS,
  FILM_CLONE_AI_STEP_GROUPS_BY_INPUT_MODE,
  FILM_CLONE_INPUT_MODE_LABELS,
  FULL_VIDEO_INPUT_MODE,
  GENERAL_SETTINGS_TAB,
  GOOGLE_AI_INPUT_MODE_BY_STEP_GROUP,
  GOOGLE_AI_PROVIDER_ID,
  MEDIA_PROVIDER_SEPARATOR,
  MEDIA_PROVIDER_SETTING_KEYS,
  ROUTES_BY_MEDIA_PROVIDER_SETTING,
  SAME_AS_AI_MODELS_OPTION_VALUE,
  SETTINGS_PATH,
  SETTINGS_TAB_OPTIONS,
  VIDEO_TO_MARKDOWN_INPUT_MODE_LABELS,
  type SettingsTab,
} from "./constants";
import type {
  AiGroupModel,
  AiModel,
  AiModelOption,
  AiModelStatus,
  AiModelsDraft,
  AiModelsUpdate,
  AiRun,
  AiRunPlan,
  AiStepGroup,
  AiStepModels,
  AiUsed,
  AppSettings,
  FilmAnalysisInputMode,
  MediaProviderSettingKey,
  MediaProviderStatus,
  ResolvedAiModel,
  ResolvedMediaProvider,
} from "./types";

export function resolveSettingsTab(requestedTab: string | undefined): SettingsTab {
  const matchingOption = SETTINGS_TAB_OPTIONS.find((option) => option.value === requestedTab);
  return matchingOption?.value ?? DEFAULT_SETTINGS_TAB;
}

export function buildSettingsPath(tab: SettingsTab): string {
  return `${SETTINGS_PATH}?tab=${tab}`;
}

export function buildProviderSettingsPath(providerId: ProviderId): string {
  return `${buildSettingsPath(GENERAL_SETTINGS_TAB)}&provider=${encodeURIComponent(providerId)}`;
}

export function buildSettingsUpdate(settings: AppSettings, draftSettings: Partial<AppSettings>): Partial<AppSettings> {
  return {
    scriptLanguage: pickChangedValue(draftSettings.scriptLanguage, settings.scriptLanguage),
    aiModel: pickChangedValue(draftSettings.aiModel, settings.aiModel, isSameAiModel),
    aiStepModels: pickChangedValue(draftSettings.aiStepModels, settings.aiStepModels, isSameStepModels),
    inputMode: pickChangedValue(draftSettings.inputMode, settings.inputMode),
    filmAnalysisInputMode: pickChangedValue(draftSettings.filmAnalysisInputMode, settings.filmAnalysisInputMode),
    filmCloneInputMode: pickChangedValue(draftSettings.filmCloneInputMode, settings.filmCloneInputMode),
    filmCloneImageProvider: pickChangedValue(draftSettings.filmCloneImageProvider, settings.filmCloneImageProvider),
    filmStudioImageProvider: pickChangedValue(draftSettings.filmStudioImageProvider, settings.filmStudioImageProvider),
    filmStudioClipProvider: pickChangedValue(draftSettings.filmStudioClipProvider, settings.filmStudioClipProvider),
  };
}

export function buildAiModelsUpdate(
  settings: AppSettings,
  providerSettings: ProviderSettings,
  draft: AiModelsDraft,
): AiModelsUpdate {
  const changedRoutes = pickChangedRoutes(providerSettings.routes, draft.routes);
  const changedModels = pickChangedModelsByProvider(providerSettings.providers, draft.modelIdsByProvider);
  return {
    aiModel: pickChangedValue(draft.settings.aiModel, settings.aiModel, isSameAiModel),
    aiStepModels: pickChangedValue(draft.settings.aiStepModels, settings.aiStepModels, isSameStepModels),
    inputMode: pickChangedValue(draft.settings.inputMode, settings.inputMode),
    filmAnalysisInputMode: pickChangedValue(draft.settings.filmAnalysisInputMode, settings.filmAnalysisInputMode),
    routes: Object.keys(changedRoutes).length > 0 ? changedRoutes : undefined,
    models: Object.keys(changedModels).length > 0 ? changedModels : undefined,
  };
}

export function hasSettingsChanges(update: Partial<AppSettings> | AiModelsUpdate): boolean {
  return Object.values(update).some((value) => value !== undefined);
}

export function describeInputMode(
  inputMode: FilmAnalysisInputMode | undefined,
  labelsByInputMode: Partial<Record<FilmAnalysisInputMode, string>>,
): string {
  return labelsByInputMode[inputMode ?? DEFAULT_INPUT_MODE] ?? EMPTY_INPUT_MODE_LABEL;
}

export function isFullVideoInputMode(inputMode: FilmAnalysisInputMode | undefined): boolean {
  return inputMode === FULL_VIDEO_INPUT_MODE;
}

export function resolveStepGroupModel(
  settings: Pick<AppSettings, "aiModel" | "aiStepModels">,
  group: AiStepGroup,
): AiModel {
  return settings.aiStepModels[group] ?? settings.aiModel;
}

export function hasOnlySameAsAllStepsModels(stepModels: AiStepModels): boolean {
  return AI_STEP_GROUPS.every((group) => stepModels[group] === null);
}

export function resolveAiModel(aiModel: AiModel, analysisProviders: readonly Provider[]): ResolvedAiModel {
  const provider = analysisProviders.find((candidate) => candidate.id === aiModel.provider);
  const catalogModel = provider?.catalog[ANALYSIS_MEDIA_KIND]?.find((model) => model.id === aiModel.model);
  return {
    label: catalogModel?.label ?? aiModel.model,
    providerName: provider?.name ?? PROVIDER_SHORT_NAMES[aiModel.provider],
    isSetUp: provider?.setUp ?? false,
  };
}

export function buildAiModelStatus(
  settings: AppSettings,
  analysisProviders: readonly Provider[],
  run: AiRun,
): AiModelStatus {
  const { groups, ...inputModeDetails } = planAiRun(settings, run);
  const groupModels = groups.map((group): AiGroupModel => {
    const aiModel = resolveStepGroupModel(settings, group);
    return {
      group,
      aiModel,
      ...resolveAiModel(aiModel, analysisProviders),
      needsGoogleAi: isGoogleAiRequired(group, inputModeDetails.inputMode) && !isGoogleAiModel(aiModel),
    };
  });
  return { groupModels, ...inputModeDetails };
}

export function isAiModelBlocked(status: AiModelStatus | undefined): boolean {
  return status?.groupModels.some((groupModel) => !groupModel.isSetUp || groupModel.needsGoogleAi) === true;
}

export function listMissingAiProviderNames(status: AiModelStatus): string[] {
  const missingGroupModels = status.groupModels.filter((groupModel) => !groupModel.isSetUp);
  return [...new Set(missingGroupModels.map((groupModel) => groupModel.providerName))];
}

export function listGroupsNeedingGoogleAi(status: AiModelStatus): AiStepGroup[] {
  return status.groupModels.filter((groupModel) => groupModel.needsGoogleAi).map((groupModel) => groupModel.group);
}

export function describeAiModelLine(status: AiModelStatus): string {
  return `AI: ${describeAiGroupModels(status.groupModels)}`;
}

export function describeInputModeLine(inputModeLabel: string): string {
  return `Input: ${inputModeLabel}`;
}

export function describeMediaProviderLine(imageProviderName: string, clipProviderName?: string): string {
  const imagePart = `Images with: ${imageProviderName}`;
  if (clipProviderName === undefined) return imagePart;
  return `${imagePart}${MEDIA_PROVIDER_SEPARATOR}Clips with: ${clipProviderName}`;
}

export function buildMissingAiKeyHint(providerName: string): string {
  return `Add the ${providerName} key in Settings → General.`;
}

export function buildGoogleAiModelHint(group: AiStepGroup): string {
  return `Pick a Google AI model for ${AI_STEP_GROUP_LABELS[group]} in Settings → AI models.`;
}

export function buildGoogleAiModelWarning(
  group: AiStepGroup,
  aiModel: AiModel,
  shownInputModes: readonly FilmAnalysisInputMode[],
): string | undefined {
  if (isGoogleAiModel(aiModel)) return undefined;
  const googleAiInputMode = shownInputModes.find((inputMode) => isGoogleAiRequired(group, inputMode));
  if (googleAiInputMode === undefined) return undefined;
  return `${FILM_ANALYSIS_INPUT_MODE_LABELS[googleAiInputMode]} needs a Google AI model here.`;
}

export function resolveMediaProvider(
  providerSettings: ProviderSettings,
  route: RouteName,
  pickedProviderId: ProviderId | null,
): ResolvedMediaProvider {
  const providerId = pickedProviderId ?? providerSettings.routes[route];
  const provider = providerSettings.providers.find((candidate) => candidate.id === providerId);
  return {
    id: providerId,
    name: provider?.name ?? PROVIDER_SHORT_NAMES[providerId],
    isSetUp: provider?.setUp ?? false,
  };
}

export function buildMediaProviderStatus(settings: AppSettings, providerSettings: ProviderSettings): MediaProviderStatus {
  return {
    filmCloneImageProvider: resolveMediaProviderSetting(settings, providerSettings, "filmCloneImageProvider"),
    filmStudioImageProvider: resolveMediaProviderSetting(settings, providerSettings, "filmStudioImageProvider"),
    filmStudioClipProvider: resolveMediaProviderSetting(settings, providerSettings, "filmStudioClipProvider"),
  };
}

export function listInUseProviderIds(
  route: RouteName,
  settings: AppSettings,
  routes: ProviderRoutes,
): ReadonlySet<ProviderId> {
  const pickedProviderIds = MEDIA_PROVIDER_SETTING_KEYS.flatMap((settingKey) => {
    const pickedProviderId = settings[settingKey];
    return ROUTES_BY_MEDIA_PROVIDER_SETTING[settingKey] === route && pickedProviderId !== null ? [pickedProviderId] : [];
  });
  return new Set([routes[route], ...pickedProviderIds]);
}

export function buildMediaProviderOptions(
  routeProviderName: string,
  providerIds: readonly ProviderId[],
): SelectableOption<string>[] {
  return [
    { value: SAME_AS_AI_MODELS_OPTION_VALUE, label: `Same as AI models (${routeProviderName})` },
    ...buildRouteOptions(providerIds),
  ];
}

export function mediaProviderToOptionValue(providerId: ProviderId | null): string {
  return providerId ?? SAME_AS_AI_MODELS_OPTION_VALUE;
}

export function optionValueToMediaProvider<TProviderId extends ProviderId>(
  optionValue: string,
  providerIds: readonly TProviderId[],
): TProviderId | null {
  return providerIds.find((providerId) => providerId === optionValue) ?? null;
}

export function aiModelToOptionValue(aiModel: AiModel): string {
  return `${aiModel.provider}${AI_MODEL_OPTION_VALUE_SEPARATOR}${aiModel.model}`;
}

export function buildAiModelOptions(analysisProviders: readonly Provider[]): AiModelOption[] {
  return AI_PROVIDER_IDS.flatMap((providerId) => {
    const provider = analysisProviders.find((candidate) => candidate.id === providerId);
    return (provider?.catalog[ANALYSIS_MEDIA_KIND] ?? []).map((catalogModel) => {
      const aiModel = { provider: providerId, model: catalogModel.id };
      return {
        value: aiModelToOptionValue(aiModel),
        label: catalogModel.label,
        group: PROVIDER_SHORT_NAMES[providerId],
        aiModel,
      };
    });
  });
}

export function describeSameAsAllStepsOption(allStepsModelLabel: string): string {
  return `Same as all steps (${allStepsModelLabel})`;
}

export function listAiUsedDescriptions<TStep extends string>(
  aiUsed: AiUsed<TStep>,
  orderedSteps: readonly TStep[],
  labelsByStep: Record<TStep, string>,
): string[] {
  return orderedSteps.flatMap((step) => {
    const usedModel = aiUsed[step];
    return usedModel ? [`${labelsByStep[step]}: ${usedModel.label}`] : [];
  });
}

export function joinAiUsedDescriptions(descriptions: readonly string[]): string {
  return descriptions.length > 0 ? descriptions.join(AI_MODEL_LIST_SEPARATOR) : EMPTY_AI_USED_LABEL;
}

function describeAiGroupModels(groupModels: readonly AiGroupModel[]): string {
  const [firstGroupModel] = groupModels;
  const isOneModel = groupModels.every(
    (groupModel) => !groupModel.needsGoogleAi && isSameAiModel(groupModel.aiModel, firstGroupModel.aiModel),
  );
  if (isOneModel) return describeResolvedAiModel(firstGroupModel);
  return groupModels
    .map((groupModel) => `${AI_STEP_GROUP_LABELS[groupModel.group]} — ${describeGroupModel(groupModel)}`)
    .join(AI_MODEL_LIST_SEPARATOR);
}

function describeGroupModel(groupModel: AiGroupModel): string {
  const modelDescription = describeResolvedAiModel(groupModel);
  return groupModel.needsGoogleAi ? `${modelDescription} — needs Google AI` : modelDescription;
}

function describeResolvedAiModel(resolvedModel: ResolvedAiModel): string {
  return resolvedModel.isSetUp ? resolvedModel.label : `${resolvedModel.label} — not set up`;
}

function planAiRun(settings: AppSettings, run: AiRun): AiRunPlan {
  switch (run.kind) {
    case "videoToMarkdown":
      return {
        groups: AI_STEP_GROUPS_BY_RUN.videoToMarkdown,
        inputMode: settings.inputMode,
        inputModeLabel: VIDEO_TO_MARKDOWN_INPUT_MODE_LABELS[settings.inputMode],
      };
    case "filmAnalysis":
      return {
        groups: FILM_ANALYSIS_AI_STEP_GROUPS_BY_INPUT_MODE[settings.filmAnalysisInputMode],
        inputMode: settings.filmAnalysisInputMode,
        inputModeLabel: FILM_ANALYSIS_INPUT_MODE_LABELS[settings.filmAnalysisInputMode],
      };
    case "filmClone":
      return {
        groups: FILM_CLONE_AI_STEP_GROUPS_BY_INPUT_MODE[settings.filmCloneInputMode],
        inputMode: settings.filmCloneInputMode,
        inputModeLabel: FILM_CLONE_INPUT_MODE_LABELS[settings.filmCloneInputMode],
      };
    case "filmAnalysisRerun":
      return { groups: AI_STEP_GROUPS_BY_RUN.filmAnalysisRerun, inputMode: run.sourceInputMode };
    case "filmScript":
      return { groups: AI_STEP_GROUPS_BY_RUN.filmScript };
  }
}

function isGoogleAiRequired(group: AiStepGroup, inputMode: FilmAnalysisInputMode | undefined): boolean {
  const googleAiInputMode = GOOGLE_AI_INPUT_MODE_BY_STEP_GROUP[group];
  return googleAiInputMode !== undefined && googleAiInputMode === inputMode;
}

function isGoogleAiModel(aiModel: AiModel): boolean {
  return aiModel.provider === GOOGLE_AI_PROVIDER_ID;
}

function isSameAiModel(leftModel: AiModel | null, rightModel: AiModel | null): boolean {
  return leftModel?.provider === rightModel?.provider && leftModel?.model === rightModel?.model;
}

function isSameStepModels(leftStepModels: AiStepModels, rightStepModels: AiStepModels): boolean {
  return AI_STEP_GROUPS.every((group) => isSameAiModel(leftStepModels[group], rightStepModels[group]));
}


function pickChangedValue<TValue>(
  draftValue: TValue | undefined,
  savedValue: TValue,
  isSameValue: (draftValue: TValue, savedValue: TValue) => boolean = Object.is,
): TValue | undefined {
  return draftValue === undefined || isSameValue(draftValue, savedValue) ? undefined : draftValue;
}

function resolveMediaProviderSetting(
  settings: AppSettings,
  providerSettings: ProviderSettings,
  settingKey: MediaProviderSettingKey,
): ResolvedMediaProvider {
  return resolveMediaProvider(providerSettings, ROUTES_BY_MEDIA_PROVIDER_SETTING[settingKey], settings[settingKey]);
}
