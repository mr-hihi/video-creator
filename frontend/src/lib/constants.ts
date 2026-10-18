export const APP_NAME = "Video Tool";

export const APP_DESCRIPTION =
  "Upload a video or paste a YouTube link and get a Markdown note with its transcript and screenshots of the key moments.";

export interface AppMenuItem {
  href: string;
  label: string;
  activePathPrefixes: readonly string[];
}

export const APP_MENU_ITEMS: readonly AppMenuItem[] = [
  { href: "/", label: "Video to Markdown", activePathPrefixes: ["/jobs/"] },
  { href: "/film-analysis", label: "Film Analysis", activePathPrefixes: ["/film-analysis/"] },
  { href: "/film-clone", label: "Film Clone", activePathPrefixes: ["/film-clone/"] },
  { href: "/films", label: "Film Studio", activePathPrefixes: ["/films/"] },
  { href: "/settings", label: "Settings", activePathPrefixes: ["/settings/"] },
];

export const FILM_STUDIO_MENU_ITEMS: readonly AppMenuItem[] = [
  { href: "/films", label: "Projects", activePathPrefixes: [] },
  { href: "/films/library", label: "Library", activePathPrefixes: [] },
];

export const FILM_ANALYSIS_DESCRIPTION =
  "Upload a film or paste a YouTube link and get prompts to recreate its characters' look and voice and shots like its scenes.";
