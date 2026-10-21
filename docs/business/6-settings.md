# 6. Cài đặt (Settings)

> One file = one domain. Every section below belongs to the **Settings** domain.

App-wide settings the user changes on one screen, `/settings`: the language Film Clone writes its scripts
in, the AI models and input modes of AI Models (domain 8), and the provider that makes the images and clips
of Film Clone and Film Studio when they do not follow the shared routes of Provider Settings (7.2). The same
screen hosts the provider connections and the media groups of Provider Settings (7.4) and the prompt presets
of Prompt Presets (2.6).

- Persona: the same single local user as domain 1. No captcha on settings routes.
- Entity: `AppSetting` (table `app_settings`).

## 6.1 Settings

### Data model — `AppSetting`

| Field | Type | Meaning |
|---|---|---|
| `key` | string(64) | primary key; one of the keys below |
| `value` | JSON | |
| `updated_at` | datetime (UTC) | |

A key without a row reads its default.

| Key | Values | Default | Used by |
|---|---|---|---|
| `scriptLanguage` | `follow_target_country` \| `vi` \| `ja` \| `ko` \| `zh` \| `en` \| `fr` \| `th` \| `hi` \| `id` | `follow_target_country` | Film Clone (5.3) |
| `aiModel` | `{ "provider", "model" }` (8.1) | `{ "provider": "claude_cli", "model": "default" }` | every AI step whose group has no model of its own (8.1) |
| `aiStepModels` | `{ "moments", "audio", "filmAnalysis", "filmScript", "filmClone" }`, each `null` or `{ "provider", "model" }` (8.1) | every group `null` | the AI steps of each group (8.1) |
| `inputMode` | `subtitles` \| `whole_video` | `subtitles` | Video to Markdown jobs (8.3) |
| `filmAnalysisInputMode` | `subtitles` \| `whole_video` \| `full_video` | `subtitles` | Film Analysis jobs (3.1, 8.3) |
| `filmCloneInputMode` | `subtitles` \| `whole_video` | `subtitles` | the stage 1 job of a film clone (5.1, 8.3) |
| `filmCloneImageProvider` | `null` \| `google_flow` \| `google` \| `fal` \| `replicate` \| `openai` \| `sd_webui` | `null` | every `image` and `edit_image` request of Film Clone (5.3, 5.4); `null` → the `image` route (7.2) |
| `filmStudioImageProvider` | as `filmCloneImageProvider` | `null` | every `image` and `edit_image` request of Film Studio (4 § Media providers); `null` → the `image` route (7.2) |
| `filmStudioClipProvider` | `null` \| `google_flow` \| `google` \| `fal` \| `replicate` | `null` | every `video` request of Film Studio (4 § Media providers); `null` → the `video` route (7.2) |

### Rules

| Rule | Result |
|---|---|
| Body is a JSON object | 422 |
| Every key is one of the keys above | 400 `Unknown setting '{key}'` |
| Every value is one of its key's values — for `aiModel` and `aiStepModels`, the rules of 8.1 | 400 `Invalid value for '{key}'` |

- A request with several keys saves all or none.
- A change applies to what is decided afterwards: a film clone past stage 3 keeps its `script_language`; a
  job keeps the input mode it was created with; an AI model change applies to every AI call that starts
  afterwards, pending runs included (8.1); a change of `filmCloneImageProvider`, `filmStudioImageProvider`
  or `filmStudioClipProvider`, or of the route it follows, applies to every request created afterwards, while
  a queued request keeps the provider it was given (4.3).
- A model whose provider is not set up, or a model of another provider for a group that needs Google AI,
  saves; creating a run that needs it then answers 409 (8.1).
- An image or clip provider that is not set up saves; its requests fail at submit (7.1).

## 6.2 Screen `/settings`

Header menu as in 1.7; every `/settings…` page highlights `Settings`. Tabs, in this order: `General`
(default) · `AI models` · `Prompt override` (2.6) · `Film Analysis` · `Film Clone` · `Film Studio`;
`?tab=general|ai-models|prompt-override|film-analysis|film-clone|film-studio` selects one. `?tab=providers`
redirects to `?tab=general`; `?tab=prompt-presets` redirects to `?tab=prompt-override` and keeps `id`.

**Field help**

- Every field of `/settings` the user can change — each select, text, number and text area of every tab, the
  provider sub-tabs included — has an `(i)` button right after its label, named `About {label}`. Read-only text
  areas (`Added by the app`, the prompts of `History`) have none. Hovering it, or focusing it
  with the keyboard, shows a tooltip with the field's help text; leaving it or pressing `Esc` hides it.
- A field's hint, when it has one, stays one short sentence under the field; the help text says what the
  field changes, where it is used and what each choice does.
- The help texts: the tables below for `General`, `Film Analysis`, `Film Clone` and `Film Studio`; 8.4 for the
  `Text` group of `AI models`; 7.4 for the provider sub-tabs and the `Images`, `Clips`, `Speech` and `Music`
  groups; 2.6 for `Prompt override`.

**Tab "General"**

| Element | Detail |
|---|---|
| `Script language` | `Follow the target country` (default), then `Vietnamese`, `Japanese`, `Korean`, `Chinese`, `English`, `French`, `Thai`, `Hindi`, `Indonesian`; hint `The language Film Clone writes scripts in.`; help `Film Clone writes the script of a clone in this language. Follow the target country: the language of the country picked in Localization, or the film's own language when no country is picked. A clone keeps the language it had when its localization was chosen. Film Studio narrates only Vietnamese, English or Japanese.` |
| `Save` | saves `Script language` with `PATCH /settings`; enabled with unsaved changes; notice `Saved` |
| Panel `Providers` | one sub-tab per provider, each with its own `Save` (7.4) |

**Tab "AI models"**

| Element | Detail |
|---|---|
| Group `Text` | `All steps`, `Apply to all steps`, one row per step group and `Video to Markdown input` (8.4) |
| Groups `Images`, `Clips`, `Speech`, `Music` | the provider of the group's route and the models of its providers (7.4) |
| `Save` | saves every group with one `PATCH /settings/ai-models`, all or none; enabled with unsaved changes; notice `Saved` |

**Tab "Film Analysis"**

| Element | Detail |
|---|---|
| `Input mode` | `Subtitles` (default) \| `Frame image + audio` \| `Full video`; hint `What the model gets from the film.`; help `Subtitles: the model reads the transcript to pick key moments, then writes the prompts from their frames. Frame image + audio: it also sees one frame per second, and Gemini hears who speaks and the sounds, which add frames — slower, and Audio needs a Google AI model. Full video: Gemini watches the whole film, compressed to 480 px and 24 fps, and writes the prompts at once — no frames or video notes, and Film analysis needs a Google AI model.` Under it, the Google AI warning of 8.4 |
| `Save` | `PATCH /settings`; enabled with unsaved changes; notice `Saved` |

**Tab "Film Clone"**

| Element | Detail |
|---|---|
| `Images with` | `Same as AI models ({provider name})` (default), then `Google Flow`, `Google AI`, `fal.ai`, `Replicate`, `OpenAI`, `Stable Diffusion WebUI / Forge`; hint `Makes the asset references and scene images of Film Clone.`; help `The provider of the asset reference images and scene images of Film Clone. Same as AI models follows the Images route of the AI models tab; another choice applies to Film Clone only. A queued image keeps the provider it was given.` |
| `Input mode` | `Subtitles` (default) \| `Frame image + audio`; hint `What the model gets from the film.`; help `Subtitles: the model reads the transcript to pick key moments. Frame image + audio: it also sees one frame per second, and Gemini hears who speaks and the sounds, which add sound shots — slower, with more calls on long videos, and Audio needs a Google AI model.` Under it, the Google AI warning of 8.4 |
| `Save` | `PATCH /settings`; enabled with unsaved changes; notice `Saved` |

**Tab "Film Studio"**

| Element | Detail |
|---|---|
| `Images with` | as on `Film Clone`; hint `Makes the reference and scene images of Film Studio.`; help `The provider of the reference images and scene images of Film Studio. Same as AI models follows the Images route of the AI models tab; another choice applies to Film Studio only. A queued image keeps the provider it was given.` |
| `Clips with` | `Same as AI models ({provider name})` (default), then `Google Flow`, `Google AI`, `fal.ai`, `Replicate`; hint `Makes the clips of Film Studio.`; help `The provider of the scene clips of Film Studio. Same as AI models follows the Clips route of the AI models tab; another choice applies to Film Studio only. A queued clip keeps the provider it was given.` |
| `Save` | `PATCH /settings`; enabled with unsaved changes; notice `Saved` |

- `{provider name}` in `Same as AI models (…)` is the provider of the `image` or `video` route (7.2), as
  saved.
- Under `Images with` or `Clips with`, when the provider it resolves to is not set up (7.1): `{provider name}
  is not set up — set it up in General.`, `General` linking to `?tab=general&provider={id}`.
- An error shows an alert with the API `detail` and keeps the input.
- Switching tab or provider sub-tab, or leaving the page, with unsaved changes → confirm `Discard unsaved
  changes?`; reloading or closing the tab → the browser's leave-page prompt.

---

## API endpoints

Same JSON and error conventions as domain 1.

```
GET   /settings            — { "scriptLanguage", "aiModel", "aiStepModels", "inputMode", "filmAnalysisInputMode", "filmCloneInputMode", "filmCloneImageProvider", "filmStudioImageProvider", "filmStudioClipProvider" } — every key, with its default when it has no row
PATCH /settings            — { key: value, … } → the same shape as GET
PATCH /settings/ai-models  — { "aiModel"?, "aiStepModels"?, "inputMode"?, "filmAnalysisInputMode"?, "routes"?: { "image"?, "video"?, "speech"?, "music"? }, "models"?: { "{provider id}": { "{media kind}": "{model id}" } } } → { "settings": the shape of GET /settings, "providers": the shape of GET /settings/providers (7) }
```

`PATCH /settings/ai-models` checks every part before it saves any: the settings by 6.1 and 8.1, the routes by
7.2, the models by 7.1 § Rules. It saves all or none.

| Route | Errors |
|---|---|
| `PATCH /settings` | 400 unknown key / invalid value · 422 not an object |
| `PATCH /settings/ai-models` | 400 unknown key / invalid value / route rules / model rules · 404 unknown provider · 422 not an object |

## Configuration

No new keys.

## Capacities

None — single-user local tool (workspace ADR W2).

## Non-goals

- Settings per user, per project or per clone; an AI model, input mode, image provider or clip provider
  chosen per run.
- A Film Clone or Film Studio choice of its own for the speech or music provider, or for the AI models.
- A history of setting changes; export or import of settings.
