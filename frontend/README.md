# Video Tool — frontend

Next.js 16 (App Router) UI for Video Tool: upload a video, follow the conversion job, preview the generated Markdown with its screenshots, and download the result as a `.zip`.

## Scripts

| Command | Purpose |
| --- | --- |
| `npm run dev` | Start the development server |
| `npm run build` | Production build |
| `npm run start` | Serve the production build |
| `npm run lint` | ESLint (Next.js + TanStack Query rules) |

## Environment

Copy `.env.example` and fill in the values. All keys are inlined into the browser bundle at build time.

| Key | Meaning |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | Base URL of the Video Tool API, e.g. `http://localhost:4020` |
| `NEXT_PUBLIC_CAPTCHA_PROVIDER` | `turnstile`, `recaptcha` or `hcaptcha` |
| `NEXT_PUBLIC_CAPTCHA_SITE_KEY` | Public site key for the chosen captcha provider |

`next dev` loads `.env` and `.env.local`; `.env.test` is read only when `NODE_ENV=test`, so the test stack gets its API URL from `run.sh`. `.env.stg` and `.env.prod` are not standard Next.js names, so the deploy step must load or copy them before `next build`.

## Structure

- `src/app` — routes (`/`, `/jobs/[id]`), root layout and providers (Redux + TanStack Query)
- `src/components/{atoms,molecules,organisms,templates}` — atomic-design UI
- `src/features/jobs` — job types, constants, TanStack Query hooks and the upload-preferences slice
- `src/store` — Redux store and typed hooks (client UI state only)
- `src/lib` — API client, query client, captcha loader and formatting helpers
