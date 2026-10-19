import type { InputMode } from "@/features/settings/types";
import type {
  AssetKind,
  AutomaticRunChoices,
  CameraAngle,
  CloneJobStep,
  CloneSourceKind,
  FilmCloneJobType,
  FilmCloneStep,
  FrameKind,
  LocalizationFlagKey,
  LocalizationFlags,
  ScriptLanguageCode,
  ShotSize,
  TargetCountryCode,
} from "./types";

export const FILM_CLONE_PATH = "/film-clone";

export const FILM_CLONE_DESCRIPTION =
  "Upload a film or paste a YouTube link and get a new script with an image for every shot, optionally moved to another country.";

export const DEFAULT_CLONE_MAX_FRAMES = 1000;
export const CLONE_MAX_FRAMES_LOWER_LIMIT = 10;
export const CLONE_MAX_FRAMES_UPPER_LIMIT = 1000;
export const CLONE_MAX_FRAMES_HINT = "One scene per frame in the script.";

const SHARED_CLONE_JOB_STEPS = ["detecting_scenes", "capturing_frames", "writing_markdown"] as const;

export const CLONE_JOB_STEPS_BY_INPUT_MODE: Record<InputMode, Record<FilmCloneJobType, readonly CloneJobStep[]>> = {
  subtitles: {
    film_clone: [
      "extracting_audio",
      "transcribing",
      "picking_moments",
      ...SHARED_CLONE_JOB_STEPS,
    ],
    youtube_film_clone: [
      "fetching_transcript",
      "picking_moments",
      "downloading_video",
      ...SHARED_CLONE_JOB_STEPS,
    ],
  },
  whole_video: {
    film_clone: [
      "extracting_audio",
      "transcribing",
      "sampling_frames",
      "picking_moments",
      ...SHARED_CLONE_JOB_STEPS,
    ],
    youtube_film_clone: [
      "fetching_transcript",
      "downloading_video",
      "sampling_frames",
      "picking_moments",
      ...SHARED_CLONE_JOB_STEPS,
    ],
  },
};

export const FILM_CLONE_STEP_LABELS: Record<FilmCloneStep, string> = {
  analyzing: "Analyzing the film",
  extracting_assets: "Extracting assets",
  analyzing_shots: "Analyzing shots",
  choosing_localization: "Waiting for localization choices",
  proposing: "Proposing replacements",
  reviewing: "Waiting for your review",
  writing_script: "Writing script",
  generating_scene_images: "Generating scene images",
};

export const CLONE_AI_STEPS: readonly FilmCloneStep[] = [
  "extracting_assets",
  "analyzing_shots",
  "proposing",
  "writing_script",
];

export const CLONE_STAGE_LABELS = ["Video notes", "Assets & shots", "Localization", "Script & images"] as const;

export const CLONE_SOURCE_LABELS: Record<CloneSourceKind, string> = {
  upload: "Upload",
  youtube: "YouTube",
};

export interface TargetCountry {
  code: TargetCountryCode;
  name: string;
  language: ScriptLanguageCode;
}

export const TARGET_COUNTRIES: readonly TargetCountry[] = [
  { code: "vn", name: "Vietnam", language: "vi" },
  { code: "jp", name: "Japan", language: "ja" },
  { code: "kr", name: "South Korea", language: "ko" },
  { code: "cn", name: "China", language: "zh" },
  { code: "us", name: "United States", language: "en" },
  { code: "gb", name: "United Kingdom", language: "en" },
  { code: "fr", name: "France", language: "fr" },
  { code: "th", name: "Thailand", language: "th" },
  { code: "in", name: "India", language: "hi" },
  { code: "id", name: "Indonesia", language: "id" },
];

export const SCRIPT_LANGUAGE_NAMES: Record<ScriptLanguageCode, string> = {
  vi: "Vietnamese",
  ja: "Japanese",
  ko: "Korean",
  zh: "Chinese",
  en: "English",
  fr: "French",
  th: "Thai",
  hi: "Hindi",
  id: "Indonesian",
};

export const FOLLOW_TARGET_COUNTRY_SETTING = "follow_target_country";
export const KEEP_ORIGINAL_COUNTRY_VALUE = "original";
export const KEEP_ORIGINAL_LABEL = "Keep original";
export const ORIGINAL_SETTING_LABEL = "Original";
export const EMPTY_VALUE_LABEL = "—";

export type TargetCountryChoice = TargetCountryCode | typeof KEEP_ORIGINAL_COUNTRY_VALUE;

export const TARGET_COUNTRY_OPTIONS: readonly { value: TargetCountryChoice; label: string }[] = [
  { value: KEEP_ORIGINAL_COUNTRY_VALUE, label: KEEP_ORIGINAL_LABEL },
  ...TARGET_COUNTRIES.map((country) => ({ value: country.code, label: country.name })),
];

export const UNTICKED_LOCALIZATION_FLAGS: LocalizationFlags = {
  changeAppearance: false,
  changeCostume: false,
  changeSetting: false,
};

export const DEFAULT_AUTOMATIC_RUN_CHOICES: AutomaticRunChoices = {
  shouldRunAutomatically: false,
  choices: { targetCountry: null, targetSetting: "", ...UNTICKED_LOCALIZATION_FLAGS },
};

export const TARGET_SETTING_LABEL = "Target setting";
export const TARGET_SETTING_HINT = "Optional. e.g. a modern Western city instead of an ancient Chinese court";

export const AUTOMATIC_RUN_LABEL = "Run every step automatically";
export const AUTOMATIC_RUN_HINT = "Skips the localization choices and the review, using the choices below.";

export interface LocalizationFlag {
  key: LocalizationFlagKey;
  label: string;
  kinds: readonly AssetKind[];
}

export const LOCALIZATION_FLAGS: readonly LocalizationFlag[] = [
  { key: "changeAppearance", label: "Appearance", kinds: ["character"] },
  { key: "changeCostume", label: "Costume", kinds: ["character", "costume"] },
  { key: "changeSetting", label: "Setting", kinds: ["location", "prop"] },
];

export const PICK_COUNTRY_HINT = "Pick a country to change how the film looks.";
export const SCRIPT_LANGUAGE_FROM_SETTINGS_LABEL = "from Settings";
export const SCRIPT_LANGUAGE_FOLLOWS_COUNTRY_LABEL = "follows the target country";

export interface AssetKindGroup {
  kind: AssetKind;
  title: string;
}

export const ASSET_KIND_GROUPS: readonly AssetKindGroup[] = [
  { kind: "character", title: "Characters" },
  { kind: "costume", title: "Costumes" },
  { kind: "prop", title: "Props" },
  { kind: "location", title: "Locations" },
];

export const ASSET_KIND_LABELS: Record<AssetKind, string> = {
  character: "Character",
  costume: "Costume",
  prop: "Prop",
  location: "Location",
};

export const SHOT_SIZE_LABELS: Record<ShotSize, string> = {
  extreme_wide: "Extreme wide",
  wide: "Wide",
  full: "Full",
  medium: "Medium",
  medium_close: "Medium close-up",
  close_up: "Close-up",
  extreme_close_up: "Extreme close-up",
};

export const CAMERA_ANGLE_LABELS: Record<CameraAngle, string> = {
  eye_level: "Eye level",
  high: "High angle",
  low: "Low angle",
  birds_eye: "Bird's-eye",
  worms_eye: "Worm's-eye",
  dutch: "Dutch angle",
  over_the_shoulder: "Over the shoulder",
  pov: "POV",
};

export const FRAME_KIND_LABELS: Record<FrameKind, string> = {
  dialogue: "Dialogue",
  scene: "Scene change",
};

export const DESCRIPTION_MAX_LENGTH = 2_000;
export const DIALOGUE_MAX_LENGTH = 2_000;
export const IMAGE_PROMPT_MAX_LENGTH = 4_000;

export const ALL_FILTER_VALUE = "all";
export const ALL_FILTER_LABEL = "All";

export const CLONE_TABS = [
  { value: "videoNotes", label: "Video notes" },
  { value: "assets", label: "Assets" },
  { value: "shots", label: "Shots" },
  { value: "localization", label: "Localization" },
  { value: "script", label: "Script" },
] as const;

export type CloneTab = (typeof CLONE_TABS)[number]["value"];

export const OPEN_LOCALIZATION_LABEL = "Open Localization";

export const QUEUED_IMAGE_LABEL = "Queued";
export const GENERATING_IMAGE_LABEL = "Generating…";
export const FAILED_IMAGE_LABEL_PREFIX = "Failed: ";
export const GENERATE_IMAGE_LABEL = "Generate";
export const REGENERATE_IMAGE_LABEL = "Regenerate";

export const DELETE_CLONE_CONFIRMATION =
  "Delete this clone? The video, frames, assets, script and images are removed.";
export const RELOCALIZE_CONFIRMATION = "Discard the localization and start again?";
export const UNKNOWN_CLONE_FAILURE_MESSAGE = "The clone failed without an error message.";
