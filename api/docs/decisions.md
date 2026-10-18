# api decisions

## A1 — Batch worker inside the API process, long-polling MySQL

- **Decision:** `BatchWorker` is a daemon thread started in the FastAPI `lifespan` when `BATCH_ENABLED=true`. It claims jobs from the `jobs` table and waits on an event with a `BATCH_POLL_INTERVAL_SEC` timeout; an upload calls `notify()` so the wait ends at once.
- **Why:** the user asked for batch work that runs only while the instance is up, with no extra broker. MySQL already holds the job state.
- **Guardrail:** do not add Redis/Celery or a cron-triggered HTTP endpoint for jobs. Run one API instance per DB (see A2); the atomic claim alone does not make several instances safe.

## A2 — Interrupted jobs are requeued, not failed

- **Decision:** on shutdown the worker sets its stop flag **before** `CommandRunner.terminate_all()`; a job whose command dies after the flag is left `processing`, and `start()` requeues every `processing` job.
- **Why:** `--reload` and restarts would otherwise mark good jobs `failed`.
- **Guardrail:** keep the order `stop → terminate_all → wait_until_stopped` in `close_container`. Running two instances against one DB would make one instance requeue the other's live job — run one instance per DB until a heartbeat exists.

## A3 — Key moments from the `claude` CLI, not the API SDK

- **Decision:** `ClaudeMomentPicker` runs `claude -p --output-format json --json-schema … --tools "" --no-session-persistence --setting-sources ""` in the system temp dir and reads `structured_output`; with frames (`whole_video`) it sends one stream-json user event and reads the final `result` event.
- **Why:** the user's Claude login is used; no API key to manage. `--json-schema` makes the reply machine-checked.
- **Guardrail:** keep `--tools ""`, the temp-dir `cwd` (outside the repo) and `--setting-sources ""`: without it the CLI loads the user's settings, so their hooks, plugins and global `CLAUDE.md` reach the prompt (seen: replies in the user's chat language). The prompt must still demand titles in the transcript's language. Do not use `--bare`: it forces `ANTHROPIC_API_KEY`.

## A4 — Local whisper.cpp for speech-to-text

- **Decision:** `whisper-cli` with `ggml-large-v3-turbo.bin`, `-oj` JSON output read with `errors="replace"`.
- **Why:** free, offline, fast on Apple Silicon; handles vi / ja / en.
- **Guardrail:** keep the 16 kHz mono PCM extraction — whisper.cpp rejects other WAV formats.

## A5 — Service depends on the repository, never on SQLAlchemy

- **Decision:** `JobRepository` opens one short session per method (`session_factory.begin()`), returns detached ORM objects (`expire_on_commit=False`).
- **Why:** services and the worker thread stay testable with a mocked repository, and no session crosses threads.
- **Guardrail:** never pass a `Session` into a service or handler.

## A6 — Timestamps as `DATETIME(6)` naive UTC

- **Decision:** `UtcDateTime` stores naive UTC with microseconds and re-tags UTC on read.
- **Why:** MySQL `DATETIME` has no offset, and second precision mis-orders jobs uploaded in the same second.
- **Guardrail:** always use `UtcDateTime` for new time columns and `sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")` in migrations.

## A7 — Film prompt passes send the frames as images and give `claude` no tool

- **Decision:** `ClaudePromptWriter` runs `claude -p --input-format stream-json --output-format stream-json --verbose --tools "" --no-session-persistence --setting-sources ""` in the system temp folder. stdin is one user event: the message, then every frame as a base64 image block after a text block with its path. The answer is the `result` of the final event, stored as is.
- **Why:** the prompts need the characters' look, which only the frames show. The video notes carry caption text from the video — untrusted — so a prompt injection must find no tool: with `Read`, a test call read a file outside its workspace. The user edits these prompts freely, so no JSON schema is imposed.
- **Guardrail:** never grant a prompt pass any tool. Every pass sends at most the provider's images per call (`*_MAX_IMAGES_PER_CALL`), spread evenly over the frames, which costs more input tokens than letting Claude open a few.

## A8 — Media generation runs in its own worker, apart from the job worker

- **Decision:** `GenerationWorker` is a second daemon thread with a 16-thread pool. It claims requests per
  provider slot (`max_concurrent`, `min_interval_s`) and keeps each request in flight while it polls the
  provider.
- **Why:** a clip or an image waits minutes on a remote provider; inside the single-file job worker it would
  block every video job, and the providers allow several requests at once.
- **Guardrail:** never submit a request that has an `external_id` again — a second submit is paid again.
  Keep Google Flow submits one at a time and at least 3 s apart whatever the pacing says.

## A9 — Provider keys encrypted in MySQL with `SETTINGS_SECRET_KEY`

- **Decision:** `SecretBox` encrypts keys with Fernet (key = SHA-256 of `SETTINGS_SECRET_KEY`) before they
  are stored; responses carry only `hasKey` / `apiKeyLast4`.
- **Why:** the user enters keys in `/settings`; a DB dump alone must not leak them.
- **Guardrail:** never log or return a key, and pass every provider error through `redact_secret` before it
  reaches `error_message` or a log line. A changed `SETTINGS_SECRET_KEY` makes stored keys unreadable
  (`keyUnreadable`); they are entered again, never guessed.

## A10 — Film clone Claude calls are schema-checked and tool-less

- **Decision:** the four clone calls use `claude -p` with `--json-schema`, stream-json input (frames as
  images where the step needs them) and `--tools ""`; the reply is normalised by pure functions before
  anything is stored.
- **Why:** the steps feed tables, so the shape must be machine-checked; the video notes carry caption text
  from the video, so the call must have no tool (A7).
- **Guardrail:** keep normalising tolerant — drop or default bad entries as 5.2–5.4 say — and fail the step
  only where the spec says (no scene for a shot).

## A11 — Film Studio stages move on request finals; Claude and ffmpeg steps run in the batch worker

- **Decision:** the generation stages of an episode are advanced by `EpisodeStageRunner.advance`, called
  from each film target's `on_final`; `writing_script` and `assembling` run as the `EpisodeStepRunner` idle
  task of the batch worker, one episode at a time, like Film Clone's Claude steps.
- **Why:** a stage ends the moment its last request is final, without a third polling thread; the long
  Claude and ffmpeg steps reuse the batch worker's shutdown handling (a step cut by shutdown runs again).
- **Guardrail:** change an episode's `status` / `step` only inside `EpisodeStageRunner` (it holds the lock).
  Read stage progress from the target columns, never from request rows.

## A12 — Gemini through its REST API, chosen per run next to the Claude CLI

- **Status:** superseded by A13.
- **Decision:** `GeminiClient` calls `streamGenerateContent?alt=sse` with `httpx` and the `google` provider's
  key; every AI call site has a Claude class and a Gemini class with the same method, picked from a
  `dict[AiModel, …]` by the model copied into the job, clone or episode at creation.
- **Why:** no new SDK dependency; the provider settings already hold the key encrypted; a run started before
  a settings change finishes on the model it started with.
- **Guardrail:** read the model from the run's copy (`options.aiModel`, `Episode.ai_model`), never from the
  settings while it runs. Keep the key out of every error (`redact_secret`) and every log line.

## A13 — One AI caller, three clients, model read when each call starts

- **Decision:** every AI step asks `AiCaller` with an `AiAsk` and `AiLimits`; it dispatches on the provider of
  the step group's `AiModelChoice` to `ClaudeCliClient`, `GeminiClient` or `OpenAiClient`. The model is read
  from Settings when each call starts (`AiStepModels`) and recorded in the run's `ai_used`; only the input mode
  is copied into `Job.options.inputMode` at creation — `inputMode` for a Video to Markdown or Film Analysis
  job, `filmCloneInputMode` for the stage 1 job of a film clone (`JobIntake.resolve_film_clone_ai_options`).
  Gemini and OpenAI are called over httpx with server-sent events.
- **Why:** one class per vendor per call site grew to twelve near-duplicate classes; a third provider and a
  model per step group would have multiplied them. Reading the model per call lets a failed step be resumed on
  another model without a new run.
- **Guardrail:** a call site never imports a vendor client — it goes through `AiCaller`. A step records
  `ai_used` before its call, so the record shows the model even when the call fails. Keep the key out of every
  error (`redact_secret`) and every log line; no retry and no fallback to another provider.

## A14 — Image and clip providers read from Settings when each request is created

- **Decision:** `filmCloneImageProvider`, `filmStudioImageProvider` and `filmStudioClipProvider` are
  `AppSetting` keys (6.1), not columns of `film_projects` or `film_clones`; `null` follows the `image` /
  `video` route of `provider_routes` (7.2). When `GenerationService.queue` creates a request it maps the
  order's kind to a `MediaFeature` (`CLONE_GENERATION_KINDS` → `FILM_CLONE`, else `FILM_STUDIO`), and
  `ProviderSettingService.pick_provider(media_kind, feature)` reads the chosen provider through
  `ChosenProviderSettings`, else the route; `speech` and `music` always follow their route. `GenerationOrder`
  carries no provider. The request keeps the provider it was given. `PATCH /settings/ai-models` lives in
  `app_settings` (`AiModelSettingService`): it checks the setting values, the routes (`validate_routes`) and
  the models (`ProviderSettingService.to_stored_models`) before it saves any, then
  `AppSettingRepository.save_ai_model_settings` writes `app_settings`, `provider_routes` and
  `providers.models` in one transaction.
- **Why:** one place decides who makes images and clips for every project and clone, as the AI models do
  (A13); a change reaches pending clones and every project without editing each one. The `AI models` tab
  saves the text models, the routes and the media models all or none.
- **Guardrail:** a call site never passes a provider — it passes the media kind and the generation kind, and
  `pick_provider` decides. `providers` reaches the settings only through the `ChosenProviderSettings`
  protocol, never by importing `app_settings`; a save that spans both modules belongs in `app_settings`.
