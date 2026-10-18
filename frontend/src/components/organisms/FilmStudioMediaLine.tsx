"use client";

import { MediaProviderLine } from "@/components/molecules/MediaProviderLine";
import { FILM_STUDIO_SETTINGS_TAB } from "@/features/settings/constants";
import { useMediaProviderStatus } from "@/features/settings/queries";

export function FilmStudioMediaLine() {
  const mediaProviderStatus = useMediaProviderStatus();

  if (!mediaProviderStatus) return null;
  return (
    <MediaProviderLine
      imageProviderName={mediaProviderStatus.filmStudioImageProvider.name}
      clipProviderName={mediaProviderStatus.filmStudioClipProvider.name}
      settingsTab={FILM_STUDIO_SETTINGS_TAB}
    />
  );
}
