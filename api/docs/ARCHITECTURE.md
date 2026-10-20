# api architecture

## Layers

```
HTTP ──▶ router.py ──▶ service.py ──▶ repository.py ──▶ MySQL (jobs)
          │ (HTTP only)   │ (rules)        (SQL only)
          │               └──▶ storage.py ──▶ storage/<job_id>/
          └── http_errors.py maps domain errors → status codes
```

`app/container.py` builds every object once in the FastAPI `lifespan` and stores it on
`app.state.container`; routers read it through `Depends` helpers. Services are never module-level singletons; only `get_settings()` is cached.

## Upload request (fast path)

```
POST /jobs/video-to-markdown ─▶ require_captcha ─▶ JobService.create_video_to_markdown_job
   ─▶ validate extension + language ─▶ JobStorage.save_source (size-capped copy)
   ─▶ JobRepository.add (status=pending) ─▶ BatchWorker.notify() ─▶ 201 Job
```

## YouTube request (fast path, one metadata call)

```
POST /jobs/youtube-to-markdown ─▶ require_captcha ─▶ YoutubeJobService.create_youtube_to_markdown_job
   ─▶ validate language ─▶ YoutubeVideoChecker: parse link ─▶ yt-dlp --dump-single-json (30 s cap)
   ─▶ reject live / too long ─▶ JobRepository.add (status=pending) ─▶ BatchWorker.notify() ─▶ 201 Job
```

## Batch worker (long polling, in-process)

```
lifespan start ─▶ requeue_processing() ─▶ thread "batch-worker":
   loop: claim_next_pending()
     ├─ got a job ─▶ handler.handle(job, report_step) ─▶ mark_done / mark_failed
     │               ─▶ finish listeners (on_job_finished) ─▶ loop at once
     ├─ none, an idle task had work (IdleTask.run_next) ─▶ loop at once
     └─ none      ─▶ wait(BATCH_POLL_INTERVAL_SEC) or until notify() ─▶ loop
lifespan stop ─▶ worker.stop() ─▶ CommandRunner.terminate_all() ─▶ join
```

- Claim = select oldest `pending` + `UPDATE … WHERE status='pending'`; `rowcount == 1` wins.
- **Critical** — run one instance per DB: `start()` requeues every `processing` row, including another live instance's job (ADR A2).
- A job interrupted by shutdown is left `processing` and requeued on the next start. It is never marked `failed`.
- One job at a time per instance.
- Idle tasks run between jobs, one unit at a time: Film Clone's `extracting_assets` / `analyzing_shots` /
  `proposing` / `writing_script` (`CloneStepRunner`). `run_next(is_stopping)` gets the worker's stop signal: a unit cut by shutdown leaves its
  clone `running` and runs again on the next start, never `failed`. A finish listener that raises is logged and
  never fails the job.

## `video_to_markdown` pipeline

| Step (`JobStep`) | Adapter | Output under `storage/<job_id>/` |
| --- | --- | --- |
| `extracting_audio` | `FfmpegMediaProcessor.probe_duration_ms` + `extract_audio` | `work/audio.wav` (16 kHz mono) |
| `transcribing` | `WhisperCppTranscriber.transcribe` | `work/transcript.json` → `Transcript` |
| `sampling_frames` (`inputMode` `whole_video` only) | `FrameSampler` → `FfmpegMediaProcessor.sample_frames` (one JPEG per second) | `samples/sample-NNNNN.jpg`, deleted when `picking_moments` ends |
| `picking_moments` | `MomentPickingSteps.pick` → `KeyMomentPicker` → `AiCaller.ask_for_json` with the `moments` model → `normalize_moments` | `VideoOutline` (title, summary, moments) |
| `capturing_frames` | `FfmpegMediaProcessor.capture_frame` | `output/images/moment-NN-[Hh]MMmSSs.jpg` |
| `writing_markdown` | `build_markdown` + `JobStorage.write_archive` | `output/<name>.md`, `result.zip` |

## `youtube_to_markdown` pipeline

| Step (`JobStep`) | Code | Output under `storage/<job_id>/` |
| --- | --- | --- |
| `fetching_transcript` | `YtDlpDownloader.read_video_info` → `select_caption_track` → `download_captions` → `json3_to_transcript`; `captionKind` saved to `options` | `work/captions.<code>.json3` → `Transcript` |
| `picking_moments` | `MomentPickingSteps.pick` (shared with `video_to_markdown`) | `VideoOutline` |
| `downloading_video` | `YtDlpDownloader.download_video` — video stream only, ≤ `YOUTUBE_VIDEO_HEIGHT`; `download_video_with_audio` for Film Analysis and Film Clone in `whole_video` and Film Analysis in `full_video`; in `whole_video` it runs before `listening_to_audio`, `sampling_frames` and `picking_moments`, once | `source.mp4` |
| `capturing_frames` | `MomentFrameCapturer.capture` (shared) | `output/images/…` |
| `writing_markdown` | `build_markdown_with_moment_links` + `JobStorage.save_result` | `output/<name>.md`, `result.zip` |

`youtube_to_markdown/` imports the shared steps (`moment_steps.py`, `markdown.py`, `transcript.py`) from
`video_to_markdown/`. Rules: [../../docs/business/1-video-to-markdown.md](../../docs/business/1-video-to-markdown.md).

`normalize_moments` clamps to `[0, duration − 500 ms]`, drops blank titles and moments < 3 s apart,
sorts, caps at `MAX_MOMENTS`. Transcript segments go under the last moment that starts at or before them.

## AI models

`app/modules/ai_models/` holds every AI call (domain 8). A call site asks `AiCaller` with an `AiAsk`
(instructions, message, labelled images, labelled audio / video files (`AttachedMedia`), optional reply schema) and `AiLimits` (total timeout, optional silence
limit, `on_output`); `AiCaller.ask_for_json` / `ask_for_text` dispatch on the provider of an `AiModelChoice`:

| Provider | Client | Transport |
| --- | --- | --- |
| `claude_cli` | `ClaudeCliClient` | `claude -p --output-format stream-json` through `CommandRunner` (`run_watched` when a silence limit is set), `--json-schema` for replies with a schema, `--model` unless `default` |
| `google` | `GeminiClient` | `streamGenerateContent?alt=sse` over httpx, `x-goog-api-key`; a body over 20 MB is never sent; each `AttachedMedia` goes through `GeminiFiles` (`gemini_files.py`: resumable upload, poll until `ACTIVE`, `fileData` part, delete after the call), video calls send `mediaResolution` LOW |
| `openai` | `OpenAiClient` | `POST /v1/responses` with `stream: true`, `store: false`, the schema as `text.format` |

`streamed_answers.py` holds the SSE reading both API clients share (timeouts, error bodies, key redacted with
`redact_secret`); `ai_images.py` scales every image to `AI_IMAGE_MAX_SIDE_PX` and re-encodes it as JPEG
(`AI_IMAGE_JPEG_QUALITY`). `AiStepModels` reads the model of a step group (`moments`, `audio`, `filmAnalysis`,
`filmScript`, `filmClone`) from Settings when each call starts — the group's own model, else `aiModel` — and
raises `AiProviderNotSetUpError` (409 at creation, a failed step during a run); `find_google_model` raises
`GoogleModelRequiredError` the same way for a group that needs Google AI (`audio` in `whole_video`,
`filmAnalysis` in `full_video`). Each AI step records the model it
started with in `ai_used` (`jobs`, `film_clones`, `film_episodes`). `whole_video` splits the samples into
windows of `CLAUDE_MAX_IMAGES_PER_CALL` / `GEMINI_MAX_IMAGES_PER_CALL` / `OPENAI_MAX_IMAGES_PER_CALL`, picked by
the provider (`moment_windows.py`). Rules: [../../docs/business/8-ai-models.md](../../docs/business/8-ai-models.md).

## Film analysis pipelines

`film_analysis` / `youtube_film_analysis` run the shared steps above with `max_frames ÷ 2` dialogue
moments — in `whole_video` with `listening_to_audio` (`AudioListener` → `normalize_audio_replies`, audio parts
of `AI_MEDIA_PART_SEC`, `audio-notes.json`) before `sampling_frames` — then:

| Step (`JobStep`) | Code | Output |
| --- | --- | --- |
| `detecting_scenes` | `FfmpegSceneDetector` (`select=gt(scene,…)` + `metadata=print:file=-`) | cut times |
| `capturing_frames` | `merge_film_frames` (dialogue → sound → scene) → `MomentFrameCapturer` | `output/images/…`, `options.frameCounts` |
| `writing_markdown` | `build_markdown[_with_moment_links]` (with `SpeakerVoices` in `whole_video`) → `job_outputs.video_notes` | no `.md`, no zip |
| `writing_character_image_prompts` / `…_voice_…` / `writing_scene_prompts` | `FilmPromptPasses` → `AiCaller.ask_for_text` with the `filmAnalysis` model | `job_outputs` rows |

`full_video` skips all of the above: `compressing_video` (`VideoCompressor` → `FfmpegMediaProcessor.compress_video`,
`compressed/part-NN.mp4`), then `FullVideoPromptPasses` send the parts to the `filmAnalysis` model, one call per
part (`FullVideoSteps.run_from_video` / `run_from_compressed`).

`film_analysis_rerun` copies `video_notes` + `images/` at creation — `compressed/` for a `full_video` source —
and runs only the three prompt steps.
Rules: [../../docs/business/3-film-analysis.md](../../docs/business/3-film-analysis.md).

## Film clone pipeline

`film_clone` / `youtube_film_clone` reuse the film analysis handlers with `CloneFrameSaver` in place of the
prompt passes (`NotesPasses` protocol, `WrittenNotes` = video notes + captured frames):

| Step | Code | Output |
| --- | --- | --- |
| end of the job | `CloneFrameSaver` | one empty `film_clone_shots` row per frame, clone `aspect` |
| job finished | `CloneJobWatcher` (finish listener; also run in the lifespan for jobs that finished before a crash) | clone `running` · `extracting_assets` or `failed` |
| `extracting_assets` (idle task) | `CloneStepRunner` + `ASSETS_REPLY_SCHEMA` → `normalize_assets` | `film_clone_assets` |
| `analyzing_shots` (idle task) | `CloneStepRunner` + `SHOTS_REPLY_SCHEMA` → `normalize_shots` | the values of `film_clone_shots`; an automatic clone gets its stored localization choices applied |
| `proposing` (idle task) | `CloneStepRunner` → `normalize_localization` | localized fields, `clone_reference_image` requests; an automatic clone with nothing changed goes on to `writing_script` |
| `reviewing` of an automatic clone | media generation worker → `CloneReferenceTarget.on_final` → `CloneReferenceCheck` | clone `running` · `writing_script` once every changed asset's reference is `done`, batch worker notified |
| `writing_script` (idle task) | `CloneStepRunner` → `normalize_script` | `film_clone_scenes`, `clone_scene_image` requests |
| `generating_scene_images` | media generation worker → `CloneSceneImageTarget.on_final` → `CloneSceneImageCheck` | clone `done` / `failed` |

`WatchedCloneAiCaller` asks `AiCaller.ask_for_json` with the `filmClone` model and the watched limits
(`CLONE_AI_SILENCE_SEC` without output, `CLONE_AI_MAX_RUN_SEC` in all). Each output line or streamed event
updates `AiActivityTracker` (in memory, per clone), which the detail route returns as `aiActivity`. Pure reply
normalising lives in `clone_replies.py`. Rules: [../../docs/business/5-film-clone.md](../../docs/business/5-film-clone.md).

## Settings & providers

- `app/modules/app_settings/` — `GET/PATCH /settings`, one row per key in `app_settings` (domain 6), and
  `PATCH /settings/ai-models` (`AiModelSettingService`), which saves the AI model settings, the routes and the
  provider models in one transaction (A14).
- `app/modules/providers/` — the provider catalog (`provider_catalog.py`, `model_catalog.py`), one row per
  provider (`ensure_providers()` in the lifespan) and the four routes of `provider_routes`. API keys are
  encrypted by `SecretBox` (Fernet, key = SHA-256 of `SETTINGS_SECRET_KEY`); only `apiKeyLast4` ever leaves
  the service. `ProviderConnectionTester` does the cheap read call of 7.3. Rules:
  [../../docs/business/7-provider-settings.md](../../docs/business/7-provider-settings.md).

## Media generation worker

```
GenerationService.queue(GenerationOrder) ─▶ pick_provider (Film Clone / Film Studio chosen provider, else the route, 6.1, 7.2) ─▶ film_generation_requests (queued)
   ─▶ GenerationTarget.mark_queued ─▶ GenerationWorker.notify()
thread "generation-worker", every FILM_WORKER_POLL_INTERVAL_SEC or on notify():
   find_due_queued ─▶ provider has a free slot (max_concurrent, min_interval_s; Flow ≥ 3 s, not paused)
   ─▶ target.is_ready ─▶ claim ─▶ ThreadPoolExecutor(16):
        get_access (key decrypted) ─▶ build_media_task ─▶ adapter.submit ─▶ store external_id
        ─▶ adapter.poll every 10 s (≤ 30 min) ─▶ write file to target.output_path ─▶ save_result ─▶ on_final
```

- One `MediaProviderAdapter` per provider (`adapters/`: `google_flow` + `google_flow_rpc`, `google_ai`, `fal`,
  `replicate`, `openai_images`, `elevenlabs`, `sd_webui` + `sd_composite`, `local_audio`); a
  `ProviderError(kind)` maps to 4.3 § Retries in `retry_policy.decide_retry`. Only `RETRYABLE` is retried —
  HTTP 5xx / 429 (`http_support.to_error_kind`) and Google Flow's own; `NO_ANSWER` (timeout, unreachable) fails
  a submit at once, and while polling `_poll_once` asks again on `RETRYABLE` / `NO_ANSWER`. The other adapters
  raise `FATAL` explicitly for everything else; the default kind stays `RETRYABLE` for the Google Flow adapter.
  Errors are passed through `redact_secret` before they are stored.
- Google Flow: `FlowWsServer` (`providers/flow_ws_server.py`, `websockets.sync`, own daemon thread) listens on
  `127.0.0.1:{FLOW_WS_PORT}` for the Chrome extension in `../extension/google-flow/`; `FlowExtensionBridge.call` sends a
  `batch_rpc` and waits for the reply by id. `GoogleFlowAdapter` uploads inputs once per file content,
  creates a Flow project per film project / film clone (`flow_project_owners.py`, fallback = the Settings
  id) and keeps captcha calls ≥ 3 s apart. A poll error never requeues a submitted request.
- More references than the model takes → passes (`task_builder.count_passes` / `build_pass_task`); the
  previous pass result is kept as `{stem}.pass{n}{suffix}` next to the target file until the request ends.
- A `clipLengthS` the model does not make → segments (`clip_segments.plan_clip_segments` /
  `task_builder.build_segment_task`): segment k starts from the last frame of segment k − 1, and
  `FfmpegClipEditor` (the `ClipEditor` port) takes that frame, then joins the segments and cuts the result at
  the scene length. Segments live in `clip-segments/` next to the target file with `plan.json` naming what
  they were made from (`ClipSegmentFolder`), so a retry or a restart makes only the missing ones.
- Restart: `requeue_unsubmitted_processing()`, then `resume_polling` for every `processing` request with an
  `external_id` — never submitted twice.
- A kind without a registered `GenerationTarget` stays `queued`. Film Clone registers
  `clone_reference_image` and `clone_scene_image`; Film Studio registers its own kinds.

## Film Studio

`app/modules/films/` owns the eight `film_*` tables of domain 4 (projects, characters, project links, styles,
voice templates, episodes, episode parts, scenes) and the seven film request kinds.

```
POST /films/episodes/{id}/start ─▶ EpisodeStageRunner.start (lock) ─▶ running @ writing_outline ─▶ BatchWorker.notify()
batch worker idle task EpisodeStepRunner (one unit per call):
   running @ writing_outline      ─▶ EpisodeOutlineWriter (filmScript model) ─▶ outline_replies ─▶ save_outline
   running @ writing_script       ─▶ EpisodeScriptWriter.write_part (first part without scenes) ─▶ script_replies
                                      ─▶ save_part_script; finished once every part has scenes
   running @ updating_story_bible ─▶ StoryBibleWriter ─▶ story_bible_replies ─▶ save_story_bible
   running @ assembling           ─▶ FfmpegEpisodeAssembler ─▶ output/{stem}.mp4 + .srt
   ─▶ EpisodeStageRunner.finish_worker_stage / finish_assembly / fail_worker_step
generation stages (references → scene images → clips → audio):
   _enter_stage queues `none` + `failed` items through FilmMediaQueue ─▶ GenerationService.queue
   generation worker ─▶ film GenerationTarget (status, file, resets) ─▶ on_final ─▶ EpisodeStageRunner.advance
   advance: queue `none`, wait while anything is queued / processing, `failed` → episode failed,
            all done → stop point (pause) or next stage
```

- `EpisodeStageRunner` holds one process-wide lock; every status change of an episode (API actions, request
  finals, the idle task) goes through it, so two threads never move the same episode.
- `paused_stop_point` remembers the stop point the episode paused at; `Continue` never pauses there again.
- The three writing steps and `assembling` run their `claude` / ffmpeg processes through
  `EpisodeStepCommands`, a `CommandRunner` of their own (the writers share an `AiCaller` built on it): `stop`
  kills them without touching job or probe processes, and `save_outline` / `save_part_script` /
  `save_story_bible` drop a reply whose episode is no longer `running` at that step.
- The writers share `story_briefs.py`: the story context of 4.2 (series, story bible, earlier episodes with
  their summaries, idea or film analysis) and the `AiCallError` → `EpisodeStepFailedError` wrapping.
- `ffmpeg_assembler.py` gives every ffmpeg / ffprobe command the whole `FILM_ASSEMBLY_TIMEOUT_SEC`, so a film
  of any length can be assembled.
- Stage state is read from the targets (`reference_status`, `image_status`, …), not from request rows, so a
  stage moves on whoever queued the request (Cast panel, scene card or the stage itself).
- The idle task also calls `advance` for running episodes whose generation stage has nothing open, which
  recovers a crash between moving `step` and queuing.
- Pure parts: `film_prompts.py` (4.1 / 4.3 prompts), `outline_replies.py`, `script_replies.py` and
  `story_bible_replies.py` (4.2 normalising), `assembly_plan.py` (4.4 timing, cues, filter graphs). Paths: `film_files.py` (`storage/films/`).
  Rules: [../../docs/business/4-film-studio.md](../../docs/business/4-film-studio.md).

## Prompt presets

`app/modules/prompt_presets/` (router → service → repository) owns `prompt_presets` and
`prompt_preset_versions`. `JobIntake` copies the chosen preset's prompts into `Job.options` when a job is
created; steps read them with `get_job_prompt`, falling back to `DEFAULT_PRESET_PROMPTS`. The text the app
appends to every prompt lives in `prompt_texts.py`, shared by the pipelines and `GET /prompt-presets/defaults`.
`ensure_default_preset()` runs in the lifespan. Rules: [../../docs/business/2-prompt-presets.md](../../docs/business/2-prompt-presets.md).

## External programs

All run through `CommandRunner.run(Command)`, which applies the timeout, converts failures into
`CommandError`, and tracks running processes so shutdown can terminate them. `run_watched(Command,
silence_limit_sec, on_output)` reads stdout line by line, kills the process after `silence_limit_sec` without
output or after `Command.timeout_sec` in all, and returns `CommandOutput` (stdout, stderr, exit code) without
raising on a non-zero exit.

| Program | Config | Timeout env |
| --- | --- | --- |
| `ffmpeg`, `ffprobe` | `FFMPEG_BIN`, `FFPROBE_BIN` | `MEDIA_TIMEOUT_SEC` |
| `whisper-cli` | `WHISPER_BIN`, `WHISPER_MODEL_PATH` | `WHISPER_TIMEOUT_SEC` |
| `ffmpeg` audio parts / video compression | `FFMPEG_BIN`, `AI_MEDIA_PART_SEC`, `FULL_VIDEO_MAX_SIDE_PX`, `FULL_VIDEO_MAX_FPS` | `MEDIA_TIMEOUT_SEC`; each Gemini call with a part `AI_AUDIO_TIMEOUT_SEC` (audio) or `FILM_PROMPT_TIMEOUT_SEC` (video), the upload included |
| `claude` (provider `claude_cli`; the model comes from Settings) | `CLAUDE_BIN` | `AI_MOMENTS_TIMEOUT_SEC` (moments), `FILM_PROMPT_TIMEOUT_SEC` (prompt passes), `FILM_SCRIPT_TIMEOUT_SEC` (each outline, part and story bible call), `CLONE_AI_SILENCE_SEC` (film clone, without output) + `CLONE_AI_MAX_RUN_SEC` (film clone, in all); `PROVIDER_TEST_TIMEOUT_SEC` for `claude auth status --json` |
| `ffmpeg` scene detection | `FFMPEG_BIN`, `FILM_SCENE_THRESHOLD` | `FILM_SCENE_TIMEOUT_SEC` |
| `yt-dlp` (dependency in `pyproject.toml`, runs with `--js-runtimes node`) | `YTDLP_BIN` | `YOUTUBE_TIMEOUT_SEC` in the worker; 30 s on the create request |

Media providers are HTTP APIs reached with one shared `httpx.Client` (timeout `300 s` per call; local servers
`LOCAL_SERVER_TIMEOUT_SEC`). The local adapter servers for OmniVoice, ACE-Step and YuE live in
`../tools/local-servers/` and run outside the API.
