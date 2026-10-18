import type { Metadata } from "next";
import { SettingsManager } from "@/components/organisms/SettingsManager";
import { SettingsTemplate } from "@/components/templates/SettingsTemplate";

export const metadata: Metadata = {
  title: "Settings",
};

export default async function SettingsPage({ searchParams }: PageProps<"/settings">) {
  const { tab, id, provider } = await searchParams;

  return (
    <SettingsTemplate>
      <SettingsManager
        requestedTab={typeof tab === "string" ? tab : undefined}
        requestedPresetId={typeof id === "string" ? id : undefined}
        requestedProviderId={typeof provider === "string" ? provider : undefined}
      />
    </SettingsTemplate>
  );
}
