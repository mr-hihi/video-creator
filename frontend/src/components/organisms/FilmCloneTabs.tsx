"use client";

import { useState } from "react";
import { PlaceholderMessage } from "@/components/atoms/PlaceholderMessage";
import { TabList } from "@/components/atoms/TabList";
import { CloneShotList } from "@/components/molecules/CloneShotList";
import { CopyButton } from "@/components/molecules/CopyButton";
import { CLONE_TABS, type CloneTab } from "@/features/filmClones/constants";
import type { FilmCloneDetail } from "@/features/filmClones/types";
import {
  aspectToFrameOrientation,
  describeMissingCloneContent,
  findFirstCloneTabWithContent,
  hasCloneTabContent,
} from "@/features/filmClones/utils";
import { CloneAssetsTab } from "./CloneAssetsTab";
import { CloneLocalizationTab } from "./CloneLocalizationTab";
import { CloneScriptTab } from "./CloneScriptTab";
import { MarkdownPreview } from "./MarkdownPreview";

interface FilmCloneTabsProps {
  clone: FilmCloneDetail;
}

export function FilmCloneTabs({ clone }: FilmCloneTabsProps) {
  const [selectedTab, setSelectedTab] = useState<CloneTab>(() => findFirstCloneTabWithContent(clone));

  return (
    <div className="flex flex-col gap-4">
      <TabList<CloneTab> label="Clone results" value={selectedTab} tabs={CLONE_TABS} onChange={setSelectedTab} />
      <CloneTabContent clone={clone} tab={selectedTab} onOpenLocalization={() => setSelectedTab("localization")} />
    </div>
  );
}

interface CloneTabContentProps {
  clone: FilmCloneDetail;
  tab: CloneTab;
  onOpenLocalization: () => void;
}

function CloneTabContent({ clone, tab, onOpenLocalization }: CloneTabContentProps) {
  if (tab === "localization") return <CloneLocalizationTab clone={clone} />;
  if (tab === "script") return <CloneScriptTab clone={clone} onOpenLocalization={onOpenLocalization} />;
  if (tab === "videoNotes" && clone.videoNotes !== null) {
    return (
      <div className="flex flex-col gap-3">
        <div className="self-end">
          <CopyButton text={clone.videoNotes} />
        </div>
        <MarkdownPreview jobId={clone.jobId} markdown={clone.videoNotes} />
      </div>
    );
  }
  if (tab === "assets" && clone.assets.length) return <CloneAssetsTab clone={clone} />;
  if (tab === "shots" && hasCloneTabContent(clone, tab)) {
    return (
      <CloneShotList
        shots={clone.shots}
        assets={clone.assets}
        jobId={clone.jobId}
        frameOrientation={aspectToFrameOrientation(clone.aspect)}
        youtubeVideoId={clone.job?.options.videoId}
      />
    );
  }
  return <PlaceholderMessage>{describeMissingCloneContent(clone)}</PlaceholderMessage>;
}
