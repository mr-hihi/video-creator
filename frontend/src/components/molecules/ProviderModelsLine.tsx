import Link from "next/link";
import { AI_MODELS_SETTINGS_TAB } from "@/features/settings/constants";
import { buildSettingsPath } from "@/features/settings/utils";

export function ProviderModelsLine() {
  return (
    <p className="text-sm text-muted">
      Pick its models in{" "}
      <Link href={buildSettingsPath(AI_MODELS_SETTINGS_TAB)} className="font-medium text-accent hover:underline">
        AI models
      </Link>
      .
    </p>
  );
}
