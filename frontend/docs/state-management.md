# State management

| State | Owner | Example |
| --- | --- | --- |
| Server data (jobs, job detail, presets, clones, settings, providers, Film Studio) | TanStack Query | `useJobsQuery(types)`, `useJobQuery(id)`, `usePromptPresetsQuery`, `usePromptPresetQuery(id)`, `usePromptDefaultsQuery`, `useFilmClonesQuery`, `useFilmCloneQuery(id)`, `useAppSettingsQuery`, `useProviderSettingsQuery(refetchIntervalMs?)` (polls only in the `General` tab, `PROVIDER_REFRESH_INTERVAL_MS`), `useAnalysisProvidersQuery` (same providers cache, no polling), `useAiModelStatus(run)` (settings + analysis providers, per step group of the run — `run` = `{ kind }` of `videoToMarkdown`, `filmAnalysis`, `filmClone`, `filmScript`, or `filmAnalysisRerun` with its `sourceInputMode`; the groups and the Google AI check follow the run's input mode), `useMediaProviderStatus` (settings + providers, the image and clip providers Film Clone and Film Studio resolve to), `useFilmProjectsQuery(status)`, `useFilmProjectQuery(id)`, `useFilmEpisodeQuery(id)`, `useFilmPartQuery(partId, isEpisodeBusy)` (only while its block is open), `useFilmCharactersQuery`, `useFilmStylesQuery`, `useFilmVoicesQuery` |
| Server mutation | TanStack Query mutation | every job creation (`useCreate…JobMutation`, incl. film analysis and rerun) shares the `creations` mutation key and invalidates `jobQueryKeys.lists()`; `useIsCreatingJob` reads any one in flight. Preset mutations invalidate `promptPresetQueryKeys.all`. `useUpdateAiModelsMutation` (`PATCH /settings/ai-models`) invalidates `appSettingQueryKeys.all` and `providerQueryKeys.all`. Film Studio mutations invalidate the `filmQueryKeys` groups they touch (`projects()`, `characters()`, `styles()`, `voices()`, `episodes()`); episode actions share the `episodeAction` mutation key and `useLatestEpisodeActionError(id)` reads the last one's error, so a start refused after a create shows on the episode page |
| Cross-component UI preference | Redux Toolkit slice | `uploadPreferences.language` |
| One component's transient state | `useState` | selected file, YouTube link, conversion source, upload percent, captcha token, chosen preset, max frames, automatic run choices of a new clone, preset draft |
| Selected preset in the `Prompt override` tab of `/settings` | URL `?id=` | `PromptPresetManager` reads it from the page, changes it with `router.replace` |
| Selected provider sub-tab in the `General` tab of `/settings` | URL `?provider=` | `ProviderSettingsPanel` reads it from the page, changes it with `router.replace` |
| Selected tab on `/settings` | URL `?tab=` | `SettingsManager` reads it from the page, changes it with `router.replace` |
| Selected tab on `/films/library` | URL `?tab=` | `FilmLibraryManager` reads it from the page, changes it with `router.replace` |
| Selected tab on `/films/[id]` | URL `?tab=` | `FilmProjectDetailPanel` reads it from the page, changes it with `router.replace` |
| Unsaved edits of a provider card | `useState` draft over the query data | `ProviderCard` keeps the draft so the 5 s refetch never wipes what the user typed; `FilmProjectSettingsForm`, `FilmScenePromptsForm` and `SavableTextAreaField` do the same over the 3 s Film Studio refetch |
| Unsaved edits inside the episode popup, the project page and `/settings` | `UnsavedChangesContext` (`lib/unsavedChanges.ts`) | each draft form calls `useUnsavedChangesReport(hasUnsavedChanges)`; `FilmEpisodePopup` provides the context and confirms `Close` / Esc while any form reports one; `FilmProjectDetailPanel` and `SettingsManager` get the reporter from `useUnsavedPageChanges()`, which also confirms leaving the page, and confirm a tab switch; without the provider the hook does nothing |

## Rules

- **Critical** — never copy query data into Redux or `useState`; read it from the hook.
- **Critical** — query keys come from the feature's key factory (`jobQueryKeys`, `filmCloneQueryKeys`, `filmQueryKeys`, `appSettingQueryKeys`, …); never inline arrays.
- **Preferred** — a slice exposes actions named as events (`languageChanged`) and `selectors`; read with `useAppSelector`.
- **Preferred** — poll with `refetchInterval` returning `false` once nothing is in progress; don't use `setInterval`.
- Redux state is not persisted across reloads.
