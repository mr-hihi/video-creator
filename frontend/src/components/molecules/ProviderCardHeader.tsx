import { Badge, type BadgeTone } from "@/components/atoms/Badge";
import { PROVIDER_KIND_LABELS } from "@/features/providers/constants";
import type { Provider, ProviderStatus } from "@/features/providers/types";
import { describeProviderQueue, describeProviderStatus, determineProviderStatus } from "@/features/providers/utils";

const PROVIDER_STATUS_TONES: Record<ProviderStatus, BadgeTone> = {
  ready: "success",
  connected: "success",
  notSetUp: "neutral",
  notConnected: "neutral",
  keyUnreadable: "danger",
  paused: "info",
  signedIn: "success",
  notSignedIn: "neutral",
  notFound: "danger",
};

interface ProviderCardHeaderProps {
  provider: Provider;
  remainingPauseSeconds: number;
}

export function ProviderCardHeader({ provider, remainingPauseSeconds }: ProviderCardHeaderProps) {
  const status = determineProviderStatus(provider, remainingPauseSeconds);

  return (
    <header className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="min-w-0 text-base font-semibold break-words">{provider.name}</h3>
        <Badge tone="neutral">{PROVIDER_KIND_LABELS[provider.kind]}</Badge>
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <Badge tone={PROVIDER_STATUS_TONES[status]}>{describeProviderStatus(status, remainingPauseSeconds)}</Badge>
        {provider.kind !== "cli" && (
          <span className="text-xs text-muted tabular-nums">{describeProviderQueue(provider.queue)}</span>
        )}
      </div>
    </header>
  );
}
