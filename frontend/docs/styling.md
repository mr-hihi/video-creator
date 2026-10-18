# Styling

Tailwind CSS v4. Tokens are CSS variables in `src/app/globals.css`, exposed as Tailwind colours via `@theme inline`.

| Token | Class |
| --- | --- |
| `--background` / `--foreground` | `bg-background` / `text-foreground` |
| `--surface` / `--border` | `bg-surface` / `border-border` |
| `--muted` | `text-muted` |
| `--accent` / `--accent-foreground` | `bg-accent text-accent-foreground` |

## Rules

- **Critical** — use token classes, never raw hex or Tailwind palette colours (`bg-blue-600`); dark mode works only through the tokens (`prefers-color-scheme` swaps them).
- **Critical** — no fixed `px` width without a responsive override; check the narrowest screen (320 px). The Turnstile widget (300 px) scrolls inside its own box.
- **Preferred** — Markdown output is styled only by the `.markdown-preview` rules in `globals.css` (`@layer components`); don't add classes through the Markdown renderer.
- **Preferred** — focus states use `focus-visible:outline-*` with the accent token.
