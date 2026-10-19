import type {
  EntityType,
  EpisodeAction,
  EpisodeSource,
  EpisodeStatus,
  EpisodeStep,
  FilmLanguage,
  Orientation,
  ProjectStatus,
  StopPoints,
  SubtitleStyle,
} from "./types";

export const FILMS_PATH = "/films";
export const FILMS_LIBRARY_PATH = "/films/library";

export const FILM_STUDIO_REFRESH_INTERVAL_MS = 3_000;

export const EPISODE_STEPS: readonly EpisodeStep[] = [
  "writing_outline",
  "writing_script",
  "updating_story_bible",
  "generating_references",
  "generating_scene_images",
  "generating_clips",
  "generating_audio",
  "assembling",
];

export const EPISODE_STEP_LABELS: Record<EpisodeStep, string> = {
  writing_outline: "Writing outline",
  writing_script: "Writing script",
  updating_story_bible: "Updating story bible",
  generating_references: "Generating reference images",
  generating_scene_images: "Generating scene images",
  generating_clips: "Generating clips",
  generating_audio: "Generating narration and music",
  assembling: "Assembling the film",
};

export const ENTITY_TYPE_LABELS: Record<EntityType, string> = {
  character: "Character",
  location: "Location",
  creature: "Creature",
  visual_asset: "Visual asset",
  generic_troop: "Generic troop",
  faction: "Faction",
};

export const LANDSCAPE_ENTITY_TYPES: ReadonlySet<EntityType> = new Set(["location"]);

export const SUBTITLE_STYLE_LABELS: Record<SubtitleStyle, string> = {
  clean_white: "Clean white",
  cinematic_gold: "Cinematic gold",
  cyber_amber: "Cyber amber",
  emerald_hud: "Emerald HUD",
};

export const DEFAULT_SUBTITLE_STYLE: SubtitleStyle = "clean_white";

export const FILM_LANGUAGE_LABELS: Record<FilmLanguage, string> = {
  vi: "Vietnamese",
  en: "English",
  ja: "Japanese",
};

export const DEFAULT_FILM_LANGUAGE: FilmLanguage = "en";

export const ORIENTATION_LABELS: Record<Orientation, string> = {
  landscape: "Landscape 16:9",
  portrait: "Portrait 9:16",
};

export const ORIENTATION_FRAME_LABELS: Record<Orientation, string> = {
  landscape: "16:9",
  portrait: "9:16",
};

export const DEFAULT_ORIENTATION: Orientation = "landscape";
export const DEFAULT_STYLE_ID = "realistic";

export const CLIP_DURATION_OPTIONS = [
  { value: "4", label: "4 s" },
  { value: "6", label: "6 s" },
  { value: "8", label: "8 s" },
  { value: "10", label: "10 s" },
  { value: "15", label: "15 s" },
  { value: "20", label: "20 s" },
  { value: "30", label: "30 s" },
] as const;

export type ClipDurationValue = (typeof CLIP_DURATION_OPTIONS)[number]["value"];

export const DEFAULT_CLIP_DURATION: ClipDurationValue = "8";

export const PROJECT_STATUS_OPTIONS: readonly { value: ProjectStatus; label: string }[] = [
  { value: "active", label: "Active" },
  { value: "archived", label: "Archived" },
];

export const ACTIVE_PROJECT_STATUS: ProjectStatus = "active";
export const DEFAULT_PROJECT_STATUS: ProjectStatus = ACTIVE_PROJECT_STATUS;

export const EMPTY_PROJECTS_MESSAGES: Record<ProjectStatus, string> = {
  active: "No projects yet",
  archived: "No archived projects",
};

export const EPISODE_SOURCE_OPTIONS: readonly { value: Exclude<EpisodeSource, "film_clone">; label: string }[] = [
  { value: "idea", label: "Idea" },
  { value: "film_analysis", label: "Film analysis" },
];

export type NewEpisodeSource = (typeof EPISODE_SOURCE_OPTIONS)[number]["value"];

export const DEFAULT_EPISODE_SOURCE: NewEpisodeSource = "idea";

export const EPISODE_SOURCE_LABELS: Record<EpisodeSource, string> = {
  idea: "Idea",
  film_analysis: "Film analysis",
  film_clone: "Film clone",
};

export const EPISODE_STATUS_LABELS: Record<EpisodeStatus, string> = {
  draft: "Draft",
  running: "Running",
  paused: "Paused",
  done: "Done",
  failed: "Failed",
};

export interface EpisodeStatusAction {
  action: EpisodeAction;
  label: string;
}

export const EPISODE_ACTION_BY_STATUS: Record<EpisodeStatus, EpisodeStatusAction> = {
  draft: { action: "start", label: "Start" },
  running: { action: "stop", label: "Stop" },
  paused: { action: "continue", label: "Continue" },
  failed: { action: "resume", label: "Resume" },
  done: { action: "assemble", label: "Assemble again" },
};

export const REWRITABLE_EPISODE_STATUSES: ReadonlySet<EpisodeStatus> = new Set(["draft", "paused", "failed"]);

export interface StopPointField {
  key: keyof StopPoints;
  label: string;
}

export const STOP_POINT_FIELDS: readonly StopPointField[] = [
  { key: "afterOutline", label: "Outline" },
  { key: "afterScript", label: "Script" },
  { key: "afterReferences", label: "Reference images" },
  { key: "afterSceneImages", label: "Scene images" },
];

export const DEFAULT_STOP_POINTS: StopPoints = {
  afterOutline: false,
  afterScript: false,
  afterReferences: false,
  afterSceneImages: true,
};

export const TARGET_DURATION_LOWER_LIMIT_S = 8;
export const DEFAULT_TARGET_DURATION_S = 60;
export const PART_DURATION_LOWER_LIMIT_S = 8;
export const PART_DURATION_UPPER_LIMIT_S = 600;
export const SCENE_CLIP_DURATION_LOWER_LIMIT_S = 4;
export const SCENE_CLIP_DURATION_UPPER_LIMIT_S = 30;

export const PROJECT_NAME_MAX_LENGTH = 100;
export const PROJECT_DESCRIPTION_MAX_LENGTH = 5_000;
export const IDEA_MAX_LENGTH = 5_000;
export const EPISODE_TITLE_MAX_LENGTH = 150;
export const PART_PLAN_MAX_LENGTH = 5_000;
export const STORY_BIBLE_MAX_LENGTH = 20_000;
export const CHARACTER_DESCRIPTION_MAX_LENGTH = 2_000;
export const IMAGE_PROMPT_MAX_LENGTH = 4_000;
export const VIDEO_PROMPT_MAX_LENGTH = 4_000;
export const NARRATION_MAX_LENGTH = 1_000;
export const EDIT_PROMPT_MAX_LENGTH = 2_000;
export const STYLE_INSTRUCTION_MAX_LENGTH = 2_000;
export const NEGATIVE_PROMPT_MAX_LENGTH = 1_000;
export const SCENE_PREFIX_MAX_LENGTH = 500;

export const ACCEPTED_IMAGE_EXTENSIONS = [".jpeg", ".jpg", ".png", ".webp"] as const;
export const ACCEPTED_AUDIO_EXTENSIONS = [".wav", ".mp3", ".m4a"] as const;

export const LIBRARY_TAB_OPTIONS = [
  { value: "characters", label: "Characters" },
  { value: "styles", label: "Styles" },
  { value: "voices", label: "Voices" },
] as const;

export type LibraryTab = (typeof LIBRARY_TAB_OPTIONS)[number]["value"];

export const DEFAULT_LIBRARY_TAB: LibraryTab = "characters";

export const PROJECT_TAB_OPTIONS = [
  { value: "overview", label: "Overview" },
  { value: "story-bible", label: "Story bible" },
] as const;

export type ProjectTab = (typeof PROJECT_TAB_OPTIONS)[number]["value"];

export const OVERVIEW_PROJECT_TAB: ProjectTab = "overview";
export const STORY_BIBLE_PROJECT_TAB: ProjectTab = "story-bible";
export const DEFAULT_PROJECT_TAB: ProjectTab = OVERVIEW_PROJECT_TAB;

export const SEARCH_BY_NAME_PLACEHOLDER = "Search by name";
export const ALL_ENTITY_TYPES_VALUE = "all";
export const ALL_ENTITY_TYPES_LABEL = "All types";

export const NO_VOICE_VALUE = "";
export const EMPTY_VALUE_LABEL = "—";
export const NEW_PROJECT_VALUE = "";
export const NEW_PROJECT_LABEL = "New project";

export const MEDIA_QUEUED_LABEL = "Queued";
export const MEDIA_GENERATING_LABEL = "Generating…";
export const MEDIA_FAILED_LABEL_PREFIX = "Failed: ";
export const MEDIA_STATUS_SEPARATOR = " · ";
export const GENERATE_LABEL = "Generate";
export const REGENERATE_LABEL = "Regenerate";

export const PREMISE_HINT = "Sent to the AI model for every episode.";
export const DEFAULT_CLIP_LENGTH_HINT =
  "For scenes you add or copy from a film clone; the script picks each scene's length.";
export const TARGET_LENGTH_HINT = `The outline splits it into parts of up to 10 minutes; the script picks each scene's length, ${SCENE_CLIP_DURATION_LOWER_LIMIT_S}-${SCENE_CLIP_DURATION_UPPER_LIMIT_S} s.`;
export const SUMMARY_HINT = "Written with the story bible after the script; later episodes read it.";
export const STORY_BIBLE_HINT =
  "The AI model reads it for every outline and part, and rewrites it after each episode's script.";
export const EMPTY_STORY_BIBLE_LABEL = "Empty — written after the first episode's script.";
export const NOT_WRITTEN_PART_LABEL = "Not written";
export const LOOK_FIXED_HINT = "Fixed once a scene image exists";
export const FILM_STUDIO_LANGUAGE_NOTICE = "Film Studio narrates only Vietnamese, English or Japanese.";
export const SEND_TO_FILM_STUDIO_LABEL = "Send to Film Studio";
export const ADD_VOICE_LABEL = "Add a voice";
export const ARCHIVED_NOTICE = "This project is archived.";
export const NEEDS_ASSEMBLY_NOTICE = "Scenes changed since the last assembly.";
export const STOP_TO_EDIT_HINT = "Stop the episode to edit.";
export const CHARACTERS_LIBRARY_HINT = "Generate reference images from a project's Cast panel.";
export const BUILT_IMAGE_PROMPT_HINT = "Left blank, it is built from the description and style.";
export const TRANSCRIBED_SAMPLE_TEXT_HINT = "Left blank, the text is transcribed from the sample.";
export const CONSENT_CLIP_HINT = "Only Google AI speech needs it: the same speaker reads Google's consent statement.";
export const DIFFERENT_STYLE_LABEL = "Different style";
export const ARCHIVED_BADGE_LABEL = "Archived";
export const BUILT_IN_BADGE_LABEL = "Built-in";
export const CONSENT_BADGE_LABEL = "Consent";
export const IDEA_LABEL = "Idea";
export const EXTRA_DIRECTION_LABEL = "Extra direction (optional)";
export const UNKNOWN_EPISODE_FAILURE_MESSAGE = "The episode failed without an error message.";
