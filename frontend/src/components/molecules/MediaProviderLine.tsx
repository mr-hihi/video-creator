import Link from "next/link";
import type { SettingsTab } from "@/features/settings/constants";
import { buildSettingsPath, describeMediaProviderLine } from "@/features/settings/utils";

interface MediaProviderLineProps {
  imageProviderName: string;
  clipProviderName?: string;
  settingsTab: SettingsTab;
}

export function MediaProviderLine({ imageProviderName, clipProviderName, settingsTab }: MediaProviderLineProps) {
  return (
    <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-sm">
      <span className="font-medium">{describeMediaProviderLine(imageProviderName, clipProviderName)}</span>
      <Link href={buildSettingsPath(settingsTab)} className="text-xs text-accent hover:underline">
        Change
      </Link>
    </p>
  );
}
