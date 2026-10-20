import type { FilmAnalysisInputMode } from "@/features/settings/types";
import type { CaptionKind, FilmAnalysisJobType, JobOutputs, JobStep, JobType, VideoToMarkdownJobType } from "./types";

export const ACCEPTED_VIDEO_EXTENSIONS = [".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"] as const;

export const UPLOAD_LANGUAGE_OPTIONS = [
  { value: "auto", label: "Auto-detect" },
  { value: "vi", label: "Vietnamese" },
  { value: "en", label: "English" },
  { value: "ja", label: "Japanese" },
] as const;

export type UploadLanguage = (typeof UPLOAD_LANGUAGE_OPTIONS)[number]["value"];

export const DEFAULT_UPLOAD_LANGUAGE: UploadLanguage = "auto";

export const CONVERSION_SOURCE_OPTIONS = [
  { value: "upload", label: "Upload file" },
  { value: "youtube", label: "YouTube link" },
] as const;

export type ConversionSource = (typeof CONVERSION_SOURCE_OPTIONS)[number]["value"];

export const DEFAULT_CONVERSION_SOURCE: ConversionSource = "upload";

export const YOUTUBE_LINK_PLACEHOLDER = "https://www.youtube.com/watch?v=…";

export const VIDEO_TO_MARKDOWN_JOB_TYPES: readonly VideoToMarkdownJobType[] = ["video_to_markdown", "youtube_to_markdown"];

export const FILM_ANALYSIS_JOB_TYPES: readonly FilmAnalysisJobType[] = [
  "film_analysis",
  "youtube_film_analysis",
  "film_analysis_rerun",
];

const PROMPT_PASS_STEPS: readonly JobStep[] = [
  "writing_character_image_prompts",
  "writing_character_voice_prompts",
  "writing_scene_prompts",
];

export const JOB_STEPS_BY_INPUT_MODE: Record<FilmAnalysisInputMode, Partial<Record<JobType, readonly JobStep[]>>> = {
  subtitles: {
    video_to_markdown: ["extracting_audio", "transcribing", "picking_moments", "capturing_frames", "writing_markdown"],
    youtube_to_markdown: [
      "fetching_transcript",
      "picking_moments",
      "downloading_video",
      "capturing_frames",
      "writing_markdown",
    ],
    film_analysis: [
      "extracting_audio",
      "transcribing",
      "picking_moments",
      "detecting_scenes",
      "capturing_frames",
      "writing_markdown",
      ...PROMPT_PASS_STEPS,
    ],
    youtube_film_analysis: [
      "fetching_transcript",
      "picking_moments",
      "downloading_video",
      "detecting_scenes",
      "capturing_frames",
      "writing_markdown",
      ...PROMPT_PASS_STEPS,
    ],
    film_analysis_rerun: PROMPT_PASS_STEPS,
  },
  whole_video: {
    video_to_markdown: [
      "extracting_audio",
      "transcribing",
      "sampling_frames",
      "picking_moments",
      "capturing_frames",
      "writing_markdown",
    ],
    youtube_to_markdown: [
      "fetching_transcript",
      "downloading_video",
      "sampling_frames",
      "picking_moments",
      "capturing_frames",
      "writing_markdown",
    ],
    film_analysis: [
      "extracting_audio",
      "transcribing",
      "listening_to_audio",
      "sampling_frames",
      "picking_moments",
      "detecting_scenes",
      "capturing_frames",
      "writing_markdown",
      ...PROMPT_PASS_STEPS,
    ],
    youtube_film_analysis: [
      "fetching_transcript",
      "downloading_video",
      "listening_to_audio",
      "sampling_frames",
      "picking_moments",
      "detecting_scenes",
      "capturing_frames",
      "writing_markdown",
      ...PROMPT_PASS_STEPS,
    ],
    film_analysis_rerun: PROMPT_PASS_STEPS,
  },
  full_video: {
    film_analysis: ["compressing_video", ...PROMPT_PASS_STEPS],
    youtube_film_analysis: ["downloading_video", "compressing_video", ...PROMPT_PASS_STEPS],
    film_analysis_rerun: PROMPT_PASS_STEPS,
  },
};

export const JOB_STEP_LABELS: Record<JobStep, string> = {
  extracting_audio: "Extracting audio",
  transcribing: "Transcribing speech",
  fetching_transcript: "Fetching YouTube transcript",
  listening_to_audio: "Listening to the audio",
  picking_moments: "Picking key moments",
  downloading_video: "Downloading video",
  compressing_video: "Compressing video",
  sampling_frames: "Sampling frames",
  detecting_scenes: "Detecting scene changes",
  capturing_frames: "Capturing frames",
  writing_markdown: "Writing Markdown",
  writing_character_image_prompts: "Writing character image prompts",
  writing_character_voice_prompts: "Writing character voice prompts",
  writing_scene_prompts: "Writing scene prompts",
};

export const JOB_SOURCE_LABELS: Record<JobType, string> = {
  video_to_markdown: "Upload",
  youtube_to_markdown: "YouTube",
  film_analysis: "Upload",
  youtube_film_analysis: "YouTube",
  film_analysis_rerun: "Rerun",
};

export const DEFAULT_MAX_FRAMES = 1000;
export const MAX_FRAMES_LOWER_LIMIT = 10;
export const MAX_FRAMES_UPPER_LIMIT = 1000;
export const MAX_FRAMES_HINT = "More frames cover more characters and scenes but take longer.";

export interface FilmResultTab {
  outputKey: keyof JobOutputs;
  label: string;
}

export const FILM_RESULT_TABS: readonly FilmResultTab[] = [
  { outputKey: "characterImagePrompts", label: "Character image prompts" },
  { outputKey: "characterVoicePrompts", label: "Character voice prompts" },
  { outputKey: "scenePrompts", label: "Scene prompts" },
  { outputKey: "videoNotes", label: "Video notes" },
];

export const WAITING_OUTPUT_MESSAGE = "Waiting…";
export const MISSING_OUTPUT_MESSAGE = "Not generated";
export const DELETED_SOURCE_LABEL = "(deleted)";
export const DELETE_ANALYSIS_CONFIRMATION = "Delete this analysis? The video, frames and prompts are removed.";

export const CAPTION_KIND_LABELS: Record<CaptionKind, string> = {
  manual: "Uploaded by author",
  auto: "Auto-generated",
};

export const UNKNOWN_CAPTION_KIND_LABEL = "—";
export const COMPLETED_JOB_STEP_LABEL = "Completed";
export const NOT_STARTED_JOB_STEP_LABEL = "Not started";
export const UNKNOWN_JOB_FAILURE_MESSAGE = "The job failed without an error message.";
