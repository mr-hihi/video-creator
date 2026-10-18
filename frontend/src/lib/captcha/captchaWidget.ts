export type CaptchaProvider = "turnstile" | "recaptcha" | "hcaptcha";

type CaptchaWidgetId = string | number;

interface CaptchaRenderOptions {
  sitekey: string;
  callback: (token: string) => void;
  "expired-callback": () => void;
  "error-callback": () => void;
}

export interface CaptchaWidgetApi {
  render(container: HTMLElement, options: CaptchaRenderOptions): CaptchaWidgetId;
  reset(widgetId?: CaptchaWidgetId): void;
  remove?(widgetId: CaptchaWidgetId): void;
}

declare global {
  interface Window {
    turnstile?: CaptchaWidgetApi;
    grecaptcha?: CaptchaWidgetApi;
    hcaptcha?: CaptchaWidgetApi;
    onCaptchaApiLoad?: () => void;
  }
}

interface CaptchaProviderDefinition {
  scriptUrl: string;
  findWidgetApi: () => CaptchaWidgetApi | undefined;
}

export type CaptchaSettings =
  | { isConfigured: true; provider: CaptchaProvider; siteKey: string }
  | { isConfigured: false; problem: string };

export interface CaptchaWidgetCallbacks {
  onToken: (token: string) => void;
  onTokenCleared: () => void;
}

export interface RenderedCaptchaWidget {
  reset: () => void;
  remove: () => void;
}

const ONLOAD_CALLBACK_NAME = "onCaptchaApiLoad";
const CAPTCHA_DISABLED_VALUE = "false";

export const IS_CAPTCHA_ENABLED = process.env.NEXT_PUBLIC_CAPTCHA_ENABLED !== CAPTCHA_DISABLED_VALUE;

const CAPTCHA_PROVIDER_DEFINITIONS: Record<CaptchaProvider, CaptchaProviderDefinition> = {
  turnstile: {
    scriptUrl: "https://challenges.cloudflare.com/turnstile/v0/api.js",
    findWidgetApi: () => window.turnstile,
  },
  recaptcha: {
    scriptUrl: "https://www.google.com/recaptcha/api.js",
    findWidgetApi: () => window.grecaptcha,
  },
  hcaptcha: {
    scriptUrl: "https://js.hcaptcha.com/1/api.js",
    findWidgetApi: () => window.hcaptcha,
  },
};

const widgetApiPromisesByProvider = new Map<CaptchaProvider, Promise<CaptchaWidgetApi>>();

export function readCaptchaSettings(): CaptchaSettings {
  const provider = process.env.NEXT_PUBLIC_CAPTCHA_PROVIDER ?? "";
  const siteKey = process.env.NEXT_PUBLIC_CAPTCHA_SITE_KEY ?? "";
  if (!isCaptchaProvider(provider)) {
    return { isConfigured: false, problem: `Unsupported NEXT_PUBLIC_CAPTCHA_PROVIDER "${provider}".` };
  }
  if (!siteKey) {
    return { isConfigured: false, problem: "NEXT_PUBLIC_CAPTCHA_SITE_KEY is not set." };
  }
  return { isConfigured: true, provider, siteKey };
}

export function loadCaptchaWidgetApi(provider: CaptchaProvider): Promise<CaptchaWidgetApi> {
  const widgetApiPromise = widgetApiPromisesByProvider.get(provider) ?? injectCaptchaScript(provider);
  widgetApiPromisesByProvider.set(provider, widgetApiPromise);
  return widgetApiPromise;
}

export function renderCaptchaWidget(
  widgetApi: CaptchaWidgetApi,
  container: HTMLElement,
  options: { siteKey: string } & CaptchaWidgetCallbacks,
): RenderedCaptchaWidget {
  const widgetId = widgetApi.render(container, {
    sitekey: options.siteKey,
    callback: options.onToken,
    "expired-callback": options.onTokenCleared,
    "error-callback": options.onTokenCleared,
  });
  return {
    reset: () => widgetApi.reset(widgetId),
    remove: () => widgetApi.remove?.(widgetId),
  };
}

function injectCaptchaScript(provider: CaptchaProvider): Promise<CaptchaWidgetApi> {
  const definition = CAPTCHA_PROVIDER_DEFINITIONS[provider];
  return new Promise((resolve, reject) => {
    window[ONLOAD_CALLBACK_NAME] = () => {
      const widgetApi = definition.findWidgetApi();
      if (widgetApi) resolve(widgetApi);
      else reject(new Error(`The ${provider} captcha script loaded without its API.`));
    };
    const script = document.createElement("script");
    script.src = buildScriptUrl(definition.scriptUrl);
    script.async = true;
    script.onerror = () => {
      widgetApiPromisesByProvider.delete(provider);
      script.remove();
      reject(new Error(`Could not load the ${provider} captcha script.`));
    };
    document.head.appendChild(script);
  });
}

function buildScriptUrl(scriptUrl: string): string {
  const url = new URL(scriptUrl);
  url.searchParams.set("render", "explicit");
  url.searchParams.set("onload", ONLOAD_CALLBACK_NAME);
  return url.toString();
}

function isCaptchaProvider(value: string): value is CaptchaProvider {
  return Object.hasOwn(CAPTCHA_PROVIDER_DEFINITIONS, value);
}
