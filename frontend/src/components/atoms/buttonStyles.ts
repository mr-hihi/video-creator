export type ButtonVariant = "primary" | "secondary";

const BASE_BUTTON_CLASS_NAME =
  "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50";

const BUTTON_VARIANT_CLASS_NAMES: Record<ButtonVariant, string> = {
  primary: "bg-accent text-accent-foreground hover:bg-accent/90 disabled:hover:bg-accent",
  secondary: "border border-border bg-surface text-foreground hover:bg-foreground/5",
};

export function buildButtonClassName(variant: ButtonVariant): string {
  return `${BASE_BUTTON_CLASS_NAME} ${BUTTON_VARIANT_CLASS_NAMES[variant]}`;
}
