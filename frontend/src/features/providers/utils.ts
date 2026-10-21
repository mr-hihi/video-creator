import {
  ANALYSIS_MEDIA_KIND,
  API_KEY_MASK,
  GOOGLE_FLOW_MIN_INTERVAL_HELP_SUFFIX,
  MIN_INTERVAL_HELP_TEXT,
  PROVIDER_NAME_PLACEHOLDER,
  PROVIDER_SHORT_NAMES,
  PROVIDER_STATUS_LABELS,
  ROUTE_FIELDS,
} from "./constants";
import type {
  CatalogModel,
  GenerationMediaKind,
  MediaKind,
  ModelIdsByKind,
  ModelIdsByProvider,
  Provider,
  ProviderDraft,
  ProviderId,
  ProviderQueue,
  ProviderRoutes,
  ProviderSettings,
  ProviderStatus,
  ProviderUpdate,
} from "./types";

const MS_PER_SECOND = 1_000;
const WHOLE_NUMBER_PATTERN = /^\d+$/;

export interface SelectableOption<TValue extends string> {
  value: TValue;
  label: string;
}

export function buildRouteOptions(providerIds: readonly ProviderId[]): SelectableOption<ProviderId>[] {
  return providerIds.map((providerId) => ({ value: providerId, label: PROVIDER_SHORT_NAMES[providerId] }));
}

export function buildModelOptions(catalogModels: readonly CatalogModel[]): SelectableOption<string>[] {
  return catalogModels.map((catalogModel) => ({ value: catalogModel.id, label: catalogModel.label }));
}

export function pickChangedRoutes(routes: ProviderRoutes, draftRoutes: Partial<ProviderRoutes>): Partial<ProviderRoutes> {
  const changedEntries = ROUTE_FIELDS.flatMap(({ route }) => {
    const draftProviderId = draftRoutes[route];
    return draftProviderId === undefined || draftProviderId === routes[route] ? [] : [[route, draftProviderId] as const];
  });
  return Object.fromEntries(changedEntries);
}

export function listRouteProviders(providers: readonly Provider[], providerIds: readonly ProviderId[]): Provider[] {
  return providerIds.flatMap((providerId) => {
    const routeProvider = providers.find((provider) => provider.id === providerId);
    return routeProvider ? [routeProvider] : [];
  });
}

export function listModelMediaKinds(
  provider: Provider,
  mediaKinds: readonly GenerationMediaKind[],
): GenerationMediaKind[] {
  return mediaKinds.filter(
    (mediaKind) => provider.mediaKinds.includes(mediaKind) && (provider.catalog[mediaKind] ?? []).length > 0,
  );
}

export function resolveSavedModelId(provider: Provider, mediaKind: MediaKind): string {
  const defaultModel = provider.catalog[mediaKind]?.find((catalogModel) => catalogModel.isDefault);
  return provider.models[mediaKind] ?? defaultModel?.id ?? "";
}

export function listAnalysisProviders(providerSettings: ProviderSettings): Provider[] {
  return providerSettings.providers.filter((provider) => provider.mediaKinds.includes(ANALYSIS_MEDIA_KIND));
}

export function resolveSelectedProvider(
  providers: readonly Provider[],
  requestedProviderId: string | undefined,
): Provider | undefined {
  return providers.find((provider) => provider.id === requestedProviderId) ?? providers[0];
}

export function buildProviderUpdate(provider: Provider, draft: ProviderDraft): ProviderUpdate {
  return {
    apiKey: draft.apiKey === "" ? undefined : draft.apiKey,
    baseUrl: toChangedOptionalText(draft.baseUrl, provider.baseUrl),
    flowProjectId: toChangedOptionalText(draft.flowProjectId, provider.flowProjectId),
    maxConcurrent: toChangedWholeNumber(draft.maxConcurrent, provider.maxConcurrent),
    minIntervalS: toChangedWholeNumber(draft.minIntervalS, provider.minIntervalS),
  };
}

export function hasProviderChanges(update: ProviderUpdate): boolean {
  return Object.values(update).some((value) => value !== undefined);
}

export function hasValidPacing(draft: ProviderDraft): boolean {
  return [draft.maxConcurrent, draft.minIntervalS].every(
    (pacingText) => pacingText === undefined || WHOLE_NUMBER_PATTERN.test(pacingText),
  );
}

export function buildApiKeyPlaceholder(provider: Provider): string | undefined {
  if (!provider.hasKey || provider.apiKeyLast4 === null) return undefined;
  return `${API_KEY_MASK}${provider.apiKeyLast4}`;
}

export function buildProviderHelpText(helpTextTemplate: string, providerName: string): string {
  return helpTextTemplate.replace(PROVIDER_NAME_PLACEHOLDER, providerName);
}

export function buildMinIntervalHelpText(provider: Provider): string {
  const helpText = buildProviderHelpText(MIN_INTERVAL_HELP_TEXT, provider.name);
  return provider.id === "google_flow" ? `${helpText}${GOOGLE_FLOW_MIN_INTERVAL_HELP_SUFFIX}` : helpText;
}

export function computeRemainingPauseSeconds(pausedUntil: string | null, referenceTimeMs: number): number {
  if (pausedUntil === null) return 0;
  return Math.max(0, Math.ceil((Date.parse(pausedUntil) - referenceTimeMs) / MS_PER_SECOND));
}

export function determineProviderStatus(provider: Provider, remainingPauseSeconds: number): ProviderStatus {
  if (provider.kind === "cli") return provider.cliStatus ?? "notFound";
  if (provider.kind === "extension") {
    if (remainingPauseSeconds > 0) return "paused";
    return provider.extensionConnected ? "connected" : "notConnected";
  }
  if (provider.keyUnreadable) return "keyUnreadable";
  return provider.setUp ? "ready" : "notSetUp";
}

export function describeProviderStatus(status: ProviderStatus, remainingPauseSeconds: number): string {
  if (status === "paused") return `Paused — resumes in ${remainingPauseSeconds} s`;
  return PROVIDER_STATUS_LABELS[status];
}

export function describeProviderQueue(queue: ProviderQueue): string {
  return `Queued ${queue.queued} · Running ${queue.processing} · Failed (24 h) ${queue.failedLast24h}`;
}

export function pickChangedModelsByProvider(
  providers: readonly Provider[],
  draftModelIdsByProvider: ModelIdsByProvider,
): ModelIdsByProvider {
  const changedEntries = providers.flatMap((provider) => {
    const changedModelIds = pickChangedModelIds(provider, draftModelIdsByProvider[provider.id] ?? {});
    return Object.keys(changedModelIds).length > 0 ? [[provider.id, changedModelIds] as const] : [];
  });
  return Object.fromEntries(changedEntries);
}

function pickChangedModelIds(provider: Provider, draftModelIdsByKind: ModelIdsByKind): ModelIdsByKind {
  const changedEntries = provider.mediaKinds.flatMap((mediaKind) => {
    const draftModelId = draftModelIdsByKind[mediaKind];
    return draftModelId === undefined || draftModelId === resolveSavedModelId(provider, mediaKind)
      ? []
      : [[mediaKind, draftModelId] as const];
  });
  return Object.fromEntries(changedEntries);
}

function toChangedOptionalText(draftText: string | undefined, savedText: string | null): string | null | undefined {
  if (draftText === undefined) return undefined;
  const trimmedText = draftText.trim();
  if (trimmedText === (savedText ?? "")) return undefined;
  return trimmedText === "" ? null : trimmedText;
}

function toChangedWholeNumber(draftText: string | undefined, savedValue: number): number | undefined {
  if (draftText === undefined || draftText === String(savedValue)) return undefined;
  return parseInt(draftText, 10);
}
