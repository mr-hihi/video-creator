import Link from "next/link";
import type { ProviderId } from "@/features/providers/types";
import { buildProviderSettingsPath } from "@/features/settings/utils";

interface ProviderSetUpLinkProps {
  providerId: ProviderId;
}

export function ProviderSetUpLink({ providerId }: ProviderSetUpLinkProps) {
  return (
    <Link href={buildProviderSettingsPath(providerId)} className="font-medium underline">
      General
    </Link>
  );
}
