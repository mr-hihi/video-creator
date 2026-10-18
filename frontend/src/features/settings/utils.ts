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
  DEFAULT_INPUT_MODE,
  DEFAULT_SETTINGS_TAB,
  EMPTY_AI_USED_LABEL,
  GENERAL_SETTINGS_TAB,
  INPUT_MODE_LABELS,
  MEDIA_PROVIDER_SEPARATOR,
  MEDIA_PROVIDER_SETTING_KEYS,
  ROUTES_BY_MEDIA_PROVIDER_SETTING,
  SAME_AS_AI_MODELS_OPTION_VALUE,
  SETTINGS_PATH,
  SETTINGS_TAB_OPTIONS,
  type SettingsTab,
} from "./constants";
import type {
  AiGroupModel,
  AiModel,
  AiModelOption,
  AiModelStatus,
  AiModelsDraft,
  AiModelsUpdate,
  AiStepGroup,
  AiStepModels,
  AiUsed,
  AppSettings,
  InputMode,
  MediaProviderSettingKey,
  MediaProviderStatus,
  ResolvedAiModel,
  ResolvedMediaProvider,
} from "./types";

const PRIMARY_MOUSE_BUTTON = 0;
const SAME_TAB_LINK_TARGETS: ReadonlySet<string> = new Set(["", "_self"]);

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

export function updateUnsavedFormKeys(
  unsavedFormKeys: ReadonlySet<string>,
  formKey: string,
  hasUnsavedChanges: boolean,
): ReadonlySet<string> {
  if (unsavedFormKeys.has(formKey) === hasUnsavedChanges) return unsavedFormKeys;
  const nextFormKeys = new Set(unsavedFormKeys);
  if (hasUnsavedChanges) nextFormKeys.add(formKey);
  else nextFormKeys.delete(formKey);
  return nextFormKeys;
}

export function isInAppNavigationClick(event: MouseEvent): boolean {
  if (event.button !== PRIMARY_MOUSE_BUTTON || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
    return false;
  }
  const link = event.target instanceof Element ? event.target.closest("a[href]") : null;
  if (!(link instanceof HTMLAnchorElement) || link.hasAttribute("download")) return false;
  const isSameTabLink = SAME_TAB_LINK_TARGETS.has(link.target);
  return isSameTabLink && link.origin === window.location.origin && link.href !== window.location.href;
}

export function buildSettingsUpdate(settings: AppSettings, draftSettings: Partial<AppSettings>): Partial<AppSettings> {
  return {
    scriptLanguage: pickChangedValue(draftSettings.scriptLanguage, settings.scriptLanguage),
    aiModel: pickChangedValue(draftSettings.aiModel, settings.aiModel, isSameAiModel),
    aiStepModels: pickChangedValue(draftSettings.aiStepModels, settings.aiStepModels, isSameStepModels),
    inputMode: pickChangedValue(draftSettings.inputMode, settings.inputMode),
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
    routes: Object.keys(changedRoutes).length > 0 ? changedRoutes : undefined,
    models: Object.keys(changedModels).length > 0 ? changedModels : undefined,
  };
}

export function hasSettingsChanges(update: Partial<AppSettings> | AiModelsUpdate): boolean {
  return Object.values(update).some((value) => value !== undefined);
}

export function describeInputMode(inputMode: InputMode | undefined): string {
  return INPUT_MODE_LABELS[inputMode ?? DEFAULT_INPUT_MODE];
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
  groups: readonly AiStepGroup[],
): AiModelStatus {
  const groupModels = groups.map((group): AiGroupModel => {
    const aiModel = resolveStepGroupModel(settings, group);
    return { group, aiModel, ...resolveAiModel(aiModel, analysisProviders) };
  });
  return { groupModels, inputMode: settings.inputMode, filmCloneInputMode: settings.filmCloneInputMode };
}

export function isAiModelBlocked(status: AiModelStatus | undefined): boolean {
  return status?.groupModels.some((groupModel) => !groupModel.isSetUp) === true;
}

export function listMissingAiProviderNames(status: AiModelStatus): string[] {
  const missingGroupModels = status.groupModels.filter((groupModel) => !groupModel.isSetUp);
  return [...new Set(missingGroupModels.map((groupModel) => groupModel.providerName))];
}

export function describeAiModelLine(status: AiModelStatus): string {
  return `AI: ${describeAiGroupModels(status.groupModels)}`;
}

export function describeInputModeLine(inputMode: InputMode): string {
  return `Input: ${describeInputMode(inputMode)}`;
}

export function describeMediaProviderLine(imageProviderName: string, clipProviderName?: string): string {
  const imagePart = `Images with: ${imageProviderName}`;
  if (clipProviderName === undefined) return imagePart;
  return `${imagePart}${MEDIA_PROVIDER_SEPARATOR}Clips with: ${clipProviderName}`;
}

export function buildMissingAiKeyHint(providerName: string): string {
  return `Add the ${providerName} key in Settings → General.`;
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
  const isOneModel = groupModels.every((groupModel) => isSameAiModel(groupModel.aiModel, firstGroupModel.aiModel));
  if (isOneModel) return describeResolvedAiModel(firstGroupModel);
  return groupModels
    .map((groupModel) => `${AI_STEP_GROUP_LABELS[groupModel.group]} — ${describeResolvedAiModel(groupModel)}`)
    .join(AI_MODEL_LIST_SEPARATOR);
}

function describeResolvedAiModel(resolvedModel: ResolvedAiModel): string {
  return resolvedModel.isSetUp ? resolvedModel.label : `${resolvedModel.label} — not set up`;
}

function isSameAiModel(leftModel: AiModel | null, rightModel: AiModel | null): boolean {
  return leftModel?.provider === rightModel?.provider && leftModel?.model === rightModel?.model;
}

function isSameStepModels(leftStepModels: AiStepModels, rightStepModels: AiStepModels): boolean {
  return AI_STEP_GROUPS.every((group) => isSameAiModel(leftStepModels[group], rightStepModels[group]));
}

function resolveStepGroupModel(settings: AppSettings, group: AiStepGroup): AiModel {
  return settings.aiStepModels[group] ?? settings.aiModel;
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
