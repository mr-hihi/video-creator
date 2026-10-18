export type ProviderId =
  | "google_flow"
  | "google"
  | "fal"
  | "replicate"
  | "openai"
  | "elevenlabs"
  | "sd_webui"
  | "omnivoice"
  | "ace_step"
  | "yue"
  | "claude_cli";

export type ProviderKind = "api" | "local" | "extension" | "cli";

export type MediaKind = "image" | "edit_image" | "video" | "speech" | "music" | "analysis";

export type GenerationMediaKind = Exclude<MediaKind, "analysis">;

export type RouteName = "image" | "video" | "speech" | "music";

export type ProviderRoutes = Record<RouteName, ProviderId>;

export type ImageRouteProviderId = Extract<
  ProviderId,
  "google_flow" | "google" | "fal" | "replicate" | "openai" | "sd_webui"
>;

export type VideoRouteProviderId = Extract<ImageRouteProviderId, "google_flow" | "google" | "fal" | "replicate">;

export type ModelIdsByKind = Partial<Record<MediaKind, string>>;

export type ModelIdsByProvider = Partial<Record<ProviderId, ModelIdsByKind>>;

export type CliStatus = "signedIn" | "notSignedIn" | "notFound";

export type ProviderStatus =
  | "ready"
  | "notSetUp"
  | "keyUnreadable"
  | "connected"
  | "notConnected"
  | "paused"
  | CliStatus;

export interface CatalogModel {
  id: string;
  label: string;
  isDefault: boolean;
  clipLengths: number[] | null;
  maxReferences: number | null;
}

export interface ProviderQueue {
  queued: number;
  processing: number;
  failedLast24h: number;
}

export interface ConnectionTest {
  ok: boolean;
  error: string | null;
  testedAt: string;
}

export interface Provider {
  id: ProviderId;
  name: string;
  kind: ProviderKind;
  mediaKinds: MediaKind[];
  hasKey: boolean;
  apiKeyLast4: string | null;
  keyUnreadable: boolean;
  baseUrl: string | null;
  models: ModelIdsByKind;
  catalog: Partial<Record<MediaKind, CatalogModel[]>>;
  maxConcurrent: number;
  minIntervalS: number;
  setUp: boolean;
  queue: ProviderQueue;
  lastTest: ConnectionTest | null;
  extensionConnected: boolean | null;
  pausedUntil: string | null;
  flowProjectId: string | null;
  cliStatus: CliStatus | null;
}

export interface ProviderSettings {
  routes: ProviderRoutes;
  providers: Provider[];
  secretKeySet: boolean;
}

export interface ProviderUpdate {
  apiKey?: string | null;
  baseUrl?: string | null;
  flowProjectId?: string | null;
  maxConcurrent?: number;
  minIntervalS?: number;
}

export interface ProviderDraft {
  apiKey: string;
  baseUrl?: string;
  flowProjectId?: string;
  maxConcurrent?: string;
  minIntervalS?: string;
}
