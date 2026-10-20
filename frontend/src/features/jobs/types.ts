import type { PresetPrompts, PresetSnapshot } from "@/features/promptPresets/types";
import type { AiUsed, FilmAnalysisInputMode } from "@/features/settings/types";

export type VideoToMarkdownJobType = "video_to_markdown" | "youtube_to_markdown";

export type FilmAnalysisJobType = "film_analysis" | "youtube_film_analysis" | "film_analysis_rerun";

export type JobType = VideoToMarkdownJobType | FilmAnalysisJobType;

export type JobStatus = "pending" | "processing" | "done" | "failed";

export type JobStep =
  | "extracting_audio"
  | "transcribing"
  | "fetching_transcript"
  | "listening_to_audio"
  | "picking_moments"
  | "downloading_video"
  | "compressing_video"
  | "sampling_frames"
  | "detecting_scenes"
  | "capturing_frames"
  | "writing_markdown"
  | "writing_character_image_prompts"
  | "writing_character_voice_prompts"
  | "writing_scene_prompts";

export type JobStepState = "completed" | "current" | "failed" | "upcoming";

export type CaptionKind = "manual" | "auto";

export interface FrameCounts {
  dialogue: number;
  sound?: number;
  scene: number;
}

export interface JobOptions {
  language: string;
  url?: string;
  videoId?: string;
  captionKind?: CaptionKind;
  maxFrames?: number;
  frameCounts?: FrameCounts;
  rerunOfJobId?: string;
  preset?: PresetSnapshot;
  prompts?: Partial<PresetPrompts>;
  inputMode?: FilmAnalysisInputMode;
}

export interface Job {
  id: string;
  type: JobType;
  status: JobStatus;
  step: JobStep | null;
  sourceFilename: string;
  options: JobOptions;
  aiUsed: AiUsed<JobStep>;
  errorMessage: string | null;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface JobOutputs {
  videoNotes: string | null;
  characterImagePrompts: string | null;
  characterVoicePrompts: string | null;
  scenePrompts: string | null;
}

export type JobDetail = Job & {
  markdown: string | null;
  outputs: JobOutputs | null;
};
