# frontend architecture

## Routes

| Route | File | Rendering | Content |
| --- | --- | --- | --- |
| `/` | `src/app/page.tsx` | static shell + client organisms | `NewConversionForm` (source switch → `UploadVideoForm` / `YoutubeLinkForm`) + `JobList` in `HomeTemplate` |
| `/jobs/[id]` | `src/app/jobs/[id]/page.tsx` | server component awaits `params`, client panel | `JobDetailPanel` in `JobDetailTemplate` |
| `/film-analysis` | `src/app/film-analysis/page.tsx` | static shell + client organisms | `NewFilmAnalysisForm` + `FilmAnalysisHistory` in `FilmAnalysisTemplate` |
| `/film-analysis/[id]` | `src/app/film-analysis/[id]/page.tsx` | server component awaits `params`, client panel | `FilmAnalysisDetailPanel` (result tabs, prompts used, rerun, `MakeFilmForm`) in `JobDetailTemplate` |
| `/film-clone` | `src/app/film-clone/page.tsx` | static shell + client organisms | `NewFilmCloneForm` (upload / YouTube) + `FilmCloneHistory` in `FilmCloneTemplate` |
| `/film-clone/[id]` | `src/app/film-clone/[id]/page.tsx` | server component awaits `params`, client panel | `FilmCloneDetailPanel` (stage bar, AI activity line, summary, `FilmCloneTabs`, `SendToFilmStudioForm`, prompts used) in `JobDetailTemplate` |
| `/films` | `src/app/films/page.tsx` | static shell + client organisms | `FilmProjectsOverview` (`FilmProjectList` + `NewFilmProjectForm`) in `FilmStudioTemplate` |
| `/films/[id]` | `src/app/films/[id]/page.tsx` | server component awaits `params`, client panel | `FilmProjectDetailPanel` (header, `FilmProjectSettingsForm`, `FilmProjectCast`, `FilmProjectEpisodes`) in `FilmStudioTemplate` |
| `/films/[id]/episodes/[number]` | `src/app/films/[id]/episodes/[number]/page.tsx` | server component awaits `params`, client panel | `FilmEpisodePanel` (loads the project, then the episode by the id its `episodes` give `number`) in `FilmStudioTemplate` |
| `/films/library` | `src/app/films/library/page.tsx` | server component awaits `searchParams.tab`, client manager | `FilmLibraryManager` (`Characters` / `Styles` / `Voices`) in `FilmStudioTemplate` |
| `/settings` | `src/app/settings/page.tsx` | server component awaits `searchParams.tab`, `searchParams.id` and `searchParams.provider`, client manager | `SettingsManager` (`General` → `GeneralSettingsForm` + `ProviderSettingsPanel` with one `ProviderCard` sub-tab per provider, `AI models` → `AiModelsSettingsForm`, `Prompt override` → `PromptPresetManager` with list, editor, history, `Film Clone` → `FilmCloneSettingsForm`, `Film Studio` → `FilmStudioSettingsForm`) in `SettingsTemplate` |

`PageTemplate` renders the header menu from `APP_MENU_ITEMS` (`lib/constants.ts`); `MenuLink` highlights the current route.
`next.config.ts` redirects `/prompt-presets` and `/settings?tab=prompt-presets` to `/settings?tab=prompt-override`,
and `/settings?tab=providers` to `/settings?tab=general`, keeping the query string.
`FilmStudioTemplate` adds the `Projects` · `Library` links (`FILM_STUDIO_MENU_ITEMS`) under it.

`src/app/layout.tsx` wraps everything in `Providers` (Redux `<Provider>` + `<QueryClientProvider>`).

## Data path

```
organism ─▶ useXxxQuery / useXxxMutation (features/jobs/queries.ts)
         ─▶ apiFetch / apiUpload (lib/api/client.ts) ─▶ NEXT_PUBLIC_API_URL
```

- `apiFetch` — JSON, default timeout 15 s (`timeoutMs` overrides), merged with the query's abort signal. Errors: `ApiError(status, detail)` or `ApiTransportError`.
- `useCreateYoutubeToMarkdownJobMutation` calls `apiFetch` with `timeoutMs` 45 s: the API checks the video with YouTube (up to 30 s) inside the request.
- `apiUpload` — `XMLHttpRequest` multipart with `onUploadProgress` (percent), default timeout 60 min.
- `getQueryClient()` — one client in the browser; retries only non-4xx errors, at most 2 times.
- Polling: list and detail refetch every 3 s (`JOB_POLL_INTERVAL_MS`) **only** while a job is `pending` / `processing`.
- Film clones poll every 3 s while a clone is `running` or `hasOpenRequests`; the `General` tab polls
  `GET /settings/providers` every 5 s (`PROVIDER_REFRESH_INTERVAL_MS`) while it is open; no other tab polls
  it. Clone frames come from `GET /jobs/{id}/files/…`, generated references and scene images from
  `GET /film-clones/files/…`.
- Film Studio: the project detail polls every 3 s while an episode is `running` or a cast reference is
  `queued` / `processing`; the episode detail while it is `running` or has `openRequests`. Images, clips,
  audio and the film come from `GET /films/files/…` (`buildFilmFileUrl`, versioned by `updatedAt`),
  downloads from `GET /films/episodes/{id}/download?file=…`. Episode creation sends `X-Captcha-Token`.

## Markdown preview

`MarkdownPreview` renders with `react-markdown` + `remark-gfm`. Its `urlTransform` rewrites relative
`img src` (`images/…`, `./images/…`) to `GET /jobs/{id}/files/…` via `resolveJobImageUrl`; an absolute image URL is not loaded — `MarkdownImage` shows its alt text, so Markdown written by Claude cannot make the browser call another host. Links render through `MarkdownLink`, which opens them in a new tab.

## Captcha

`Captcha` molecule → `lib/captcha/captchaWidget.ts` loads the provider script
(`?render=explicit&onload=onCaptchaApiLoad`), renders the widget, reports `onToken` / `onTokenCleared`,
and exposes `reset()` through a ref. The form resets it after every submit (tokens are single-use).

## Env

| Key | Use |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | API base URL; blank = same origin |
| `NEXT_PUBLIC_CAPTCHA_ENABLED` | `false` hides the widget and sends no token (`IS_CAPTCHA_ENABLED`); must match the api's `CAPTCHA_ENABLED` |
| `NEXT_PUBLIC_CAPTCHA_PROVIDER` | `turnstile` / `recaptcha` (v2) / `hcaptcha` |
| `NEXT_PUBLIC_CAPTCHA_SITE_KEY` | public site key |
