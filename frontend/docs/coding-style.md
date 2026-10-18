# frontend coding style (delta)

| Tool | Config | Command |
| --- | --- | --- |
| ESLint 9 flat config | `eslint.config.mjs`: `next/core-web-vitals`, `next/typescript`, `@tanstack/eslint-plugin-query` `flat/recommended` | `npm run lint` |
| TypeScript | `tsconfig.json` (strict) — checked by `next build` | `npm run build` |

- **Critical** — `npm run lint` and `npm run build` pass with zero errors and zero warnings.
- **Preferred** — scope a rule override to one file in `eslint.config.mjs` (only `MarkdownImage.tsx` turns off `@next/next/no-img-element`, because Markdown images come from the API at unknown sizes).
- No Prettier is configured; match the formatting of neighbouring files.
