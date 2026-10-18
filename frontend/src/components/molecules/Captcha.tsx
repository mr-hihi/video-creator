"use client";

import { useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";
import { ErrorAlert } from "@/components/atoms/ErrorAlert";
import {
  IS_CAPTCHA_ENABLED,
  loadCaptchaWidgetApi,
  readCaptchaSettings,
  renderCaptchaWidget,
  type CaptchaWidgetCallbacks,
  type RenderedCaptchaWidget,
} from "@/lib/captcha/captchaWidget";

export interface CaptchaHandle {
  reset: () => void;
}

interface CaptchaProps extends CaptchaWidgetCallbacks {
  ref?: Ref<CaptchaHandle>;
}

const captchaSettings = readCaptchaSettings();

export function Captcha({ ref, onToken, onTokenCleared }: CaptchaProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetRef = useRef<RenderedCaptchaWidget | undefined>(undefined);
  const callbacksRef = useRef<CaptchaWidgetCallbacks>({ onToken, onTokenCleared });
  const [loadErrorMessage, setLoadErrorMessage] = useState("");

  useEffect(() => {
    callbacksRef.current = { onToken, onTokenCleared };
  });

  useImperativeHandle(ref, () => ({ reset: () => widgetRef.current?.reset() }), []);

  useEffect(() => {
    if (!IS_CAPTCHA_ENABLED || !captchaSettings.isConfigured) return;
    const { provider, siteKey } = captchaSettings;
    let isEffectActive = true;
    let renderedWidget: RenderedCaptchaWidget | undefined;

    loadCaptchaWidgetApi(provider).then(
      (widgetApi) => {
        if (!isEffectActive || !containerRef.current) return;
        renderedWidget = renderCaptchaWidget(widgetApi, containerRef.current, {
          siteKey,
          onToken: (token) => callbacksRef.current.onToken(token),
          onTokenCleared: () => callbacksRef.current.onTokenCleared(),
        });
        widgetRef.current = renderedWidget;
      },
      (error: Error) => {
        if (isEffectActive) setLoadErrorMessage(error.message);
      },
    );

    return () => {
      isEffectActive = false;
      renderedWidget?.remove();
      widgetRef.current = undefined;
    };
  }, []);

  if (!IS_CAPTCHA_ENABLED) return null;
  if (!captchaSettings.isConfigured) return <ErrorAlert>{captchaSettings.problem}</ErrorAlert>;
  if (loadErrorMessage) return <ErrorAlert>{loadErrorMessage}</ErrorAlert>;
  return <div ref={containerRef} className="max-w-full overflow-x-auto" />;
}
