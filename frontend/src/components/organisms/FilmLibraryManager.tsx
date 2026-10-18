"use client";

import { useRouter } from "next/navigation";
import { TabList } from "@/components/atoms/TabList";
import { LIBRARY_TAB_OPTIONS, type LibraryTab } from "@/features/films/constants";
import { buildFilmLibraryPath, resolveLibraryTab } from "@/features/films/utils";
import { FilmCharacterLibrary } from "./FilmCharacterLibrary";
import { FilmStyleLibrary } from "./FilmStyleLibrary";
import { FilmVoiceLibrary } from "./FilmVoiceLibrary";

interface FilmLibraryManagerProps {
  requestedTab: string | undefined;
}

export function FilmLibraryManager({ requestedTab }: FilmLibraryManagerProps) {
  const router = useRouter();
  const selectedTab = resolveLibraryTab(requestedTab);

  function selectTab(tab: LibraryTab) {
    if (tab === selectedTab) return;
    router.replace(buildFilmLibraryPath(tab), { scroll: false });
  }

  return (
    <div className="flex flex-col gap-6">
      <TabList label="Library" value={selectedTab} tabs={LIBRARY_TAB_OPTIONS} onChange={selectTab} />
      {selectedTab === "characters" && <FilmCharacterLibrary />}
      {selectedTab === "styles" && <FilmStyleLibrary />}
      {selectedTab === "voices" && <FilmVoiceLibrary />}
    </div>
  );
}
