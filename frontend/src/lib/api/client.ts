const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

const DEFAULT_REQUEST_TIMEOUT_MS = 15_000;
const DEFAULT_UPLOAD_TIMEOUT_MS = 60 * 60 * 1000;
const HTTP_STATUS_OK = 200;
const HTTP_STATUS_NO_CONTENT = 204;
const HTTP_STATUS_MULTIPLE_CHOICES = 300;
const HTTP_STATUS_BAD_REQUEST = 400;
const HTTP_STATUS_NOT_FOUND = 404;
const HTTP_STATUS_INTERNAL_SERVER_ERROR = 500;
const PERCENT_SCALE = 100;

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }

  get isClientError(): boolean {
    return this.status >= HTTP_STATUS_BAD_REQUEST && this.status < HTTP_STATUS_INTERNAL_SERVER_ERROR;
  }
}

export class ApiTransportError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ApiTransportError";
  }
}

export interface ApiRequestInit extends RequestInit {
  timeoutMs?: number;
}

export interface ApiUploadInit {
  body: FormData;
  headers?: Record<string, string>;
  timeoutMs?: number;
  onUploadProgress?: (uploadedPercent: number) => void;
}

interface ErrorResponseBody {
  detail: unknown;
}

interface ValidationIssue {
  msg: string;
}

export function isNotFoundError(error: unknown): boolean {
  return error instanceof ApiError && error.status === HTTP_STATUS_NOT_FOUND;
}

export function buildApiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export function buildJobFileUrl(jobId: string, relativePath: string): string {
  const encodedPath = relativePath.split("/").map(encodeURIComponent).join("/");
  return buildApiUrl(`/jobs/${encodeURIComponent(jobId)}/files/${encodedPath}`);
}

export function buildJobDownloadUrl(jobId: string): string {
  return buildApiUrl(`/jobs/${encodeURIComponent(jobId)}/download`);
}

export function buildPromptPresetExportUrl(presetId: string): string {
  return buildApiUrl(`/prompt-presets/${encodeURIComponent(presetId)}/export`);
}

export async function apiFetch<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const { timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS, headers, signal, ...requestInit } = init;
  const url = buildApiUrl(path);
  const res = await sendRequest(url, timeoutMs, {
    ...requestInit,
    signal: combineWithTimeout(timeoutMs, signal),
    headers: { "Content-Type": "application/json", ...headers },
  });
  if (!res.ok) {
    throw new ApiError(res.status, extractErrorDetail(await res.text(), describeStatus(res.status, res.statusText)));
  }
  if (res.status === HTTP_STATUS_NO_CONTENT) return undefined as T;
  return res.json() as Promise<T>;
}

export function apiUpload<T>(path: string, init: ApiUploadInit): Promise<T> {
  const { body, headers = {}, timeoutMs = DEFAULT_UPLOAD_TIMEOUT_MS, onUploadProgress } = init;
  const url = buildApiUrl(path);
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.timeout = timeoutMs;
    Object.entries(headers).forEach(([name, value]) => xhr.setRequestHeader(name, value));
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onUploadProgress?.(toPercent(event.loaded, event.total));
    };
    xhr.onload = () => settleUpload<T>(xhr, resolve, reject);
    xhr.onerror = () => reject(new ApiTransportError(describeUnreachable(url)));
    xhr.ontimeout = () => reject(new ApiTransportError(describeTimeout(url, timeoutMs)));
    xhr.send(body);
  });
}

async function sendRequest(url: string, timeoutMs: number, init: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (error) {
    throw toTransportError(error, url, timeoutMs);
  }
}

function combineWithTimeout(timeoutMs: number, callerSignal: AbortSignal | null | undefined): AbortSignal {
  const timeoutSignal = AbortSignal.timeout(timeoutMs);
  if (!callerSignal) return timeoutSignal;
  return AbortSignal.any([timeoutSignal, callerSignal]);
}

function toTransportError(error: unknown, url: string, timeoutMs: number): unknown {
  if (!(error instanceof Error)) return error;
  if (error.name === "AbortError") return error;
  if (error.name === "TimeoutError") return new ApiTransportError(describeTimeout(url, timeoutMs));
  return new ApiTransportError(describeUnreachable(url));
}

function settleUpload<T>(xhr: XMLHttpRequest, resolve: (value: T) => void, reject: (reason: Error) => void): void {
  const fallbackDetail = describeStatus(xhr.status, xhr.statusText);
  if (!isSuccessStatus(xhr.status)) {
    reject(new ApiError(xhr.status, extractErrorDetail(xhr.responseText, fallbackDetail)));
    return;
  }
  try {
    resolve(JSON.parse(xhr.responseText) as T);
  } catch {
    reject(new ApiError(xhr.status, fallbackDetail));
  }
}

function extractErrorDetail(responseBody: string, fallbackDetail: string): string {
  try {
    const parsedBody: unknown = JSON.parse(responseBody);
    if (!isErrorResponseBody(parsedBody)) return fallbackDetail;
    return formatErrorDetail(parsedBody.detail);
  } catch {
    return fallbackDetail;
  }
}

function formatErrorDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map(formatErrorDetail).join("; ");
  if (isValidationIssue(detail)) return detail.msg;
  return JSON.stringify(detail);
}

function isErrorResponseBody(value: unknown): value is ErrorResponseBody {
  return typeof value === "object" && value !== null && "detail" in value;
}

function isValidationIssue(value: unknown): value is ValidationIssue {
  return typeof value === "object" && value !== null && "msg" in value && typeof value.msg === "string";
}

function isSuccessStatus(status: number): boolean {
  return status >= HTTP_STATUS_OK && status < HTTP_STATUS_MULTIPLE_CHOICES;
}

function toPercent(loaded: number, total: number): number {
  return Math.round((loaded / total) * PERCENT_SCALE);
}

function describeStatus(status: number, statusText: string): string {
  return `API ${status}: ${statusText || "request failed"}`;
}

function describeUnreachable(url: string): string {
  return `Could not reach ${url}. Check that the API is running.`;
}

function describeTimeout(url: string, timeoutMs: number): string {
  return `Request to ${url} timed out after ${timeoutMs} ms.`;
}
