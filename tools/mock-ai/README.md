# Mock AI models

Stand-ins for every AI the API calls — the `claude` CLI, Gemini, OpenAI and whisper.cpp — so the test stack
(`APP_ENV=test`) can run every job type end to end without credit, keys or a signed-in CLI. Nothing in the
API changes: it reaches the mocks through the same clients it uses for the real services.

| Mock | Replaces | How the API reaches it |
|---|---|---|
| `mock_ai.py serve` | Gemini `streamGenerateContent` and Files API, OpenAI `/v1/responses` | `HTTPS_PROXY` points at the mock. It answers for `generativelanguage.googleapis.com` and `api.openai.com` under its own certificate, trusted through `SSL_CERT_FILE`, and tunnels every other host (YouTube, media providers) untouched |
| `mock_claude.py` | the `claude` CLI: `-p` with text or stream-json input, `auth status --json` | `CLAUDE_BIN` |
| `mock_whisper.py` | `whisper-cli -oj` | `WHISPER_BIN` and a placeholder `WHISPER_MODEL_PATH` |

## Answers

Each answer follows the reply schema and the message the API sends, so every step passes the API's checks:

| Step | Answer |
|---|---|
| Key moments | Up to the asked count, spread over the transcript lines and frame times of the message (or of the window). Title `Mock video title` and a summary naming the model and the line and frame counts for the first window; `Mock title of the part from {mm:ss}` for later windows |
| Speakers and sounds (`listening_to_audio`) | Speakers `Speaker A` and `Speaker B`, each with a short English voice; every `[{ms}ms]` transcript line of the message given to them in turn; three sounds — `action`, `ambient`, `music` — at ¼, ½ and ¾ of the range in `This part of the film runs from {start} to {end}.` (00:00–01:00 without it) |
| Film Analysis passes | Markdown with one `## Mock character {n}` or `## Mock shot {n} — {frame}` heading per item. With a video part (`full_video`), each answer names it: `seen in the video part {start}–{end}`, `Heard in the video part …`, `## Mock shot 1 — the video part …` |
| Clone assets / shots / localization / script | One asset per kind with the attached frames; one shot per frame using the listed assets; the first candidate changed; one scene per listed `shotId` |
| Film Studio outline | `Mock part {k}` parts of up to 600 s that add up to the asked length, with a logline, music and thumbnail prompt |
| Film Studio part script | A recap and enough scenes of the typical clip length (`durationS`) to fill the part's length, the first cast name (or `Mock Keeper`), the first reference frame, no narration when narration is off |
| Film Studio story bible | `Mock summary of episode {n}.` and the current story bible plus the line `E{n} — the mock cast moves the story on.` |
| whisper | One line every 10 s of the WAV, `Mock line at {mm:ss}.` |

Any other schema gets a value filled from the schema itself.

Every call is appended to `calls.jsonl` in the state directory: the model, the start of the instructions and
the message, the schema keys, each image's label and decoded JPEG size, and per vendor the URL, whether the key
was sent and where (`apiKeyLast4`, `isKeyInUrl`), `generationConfig`, `stream`, `store`, `text.format`,
`--model` and `--include-partial-messages`. A Gemini call also lists its `media`: per `fileData` part the
`label` (the text part before it, e.g. `[audio 00:00–30:00]`), `mimeType`, `fileUri`, `videoMetadata`,
`isKnownFile` and `polledState` — what the last poll of that file reported before the call.

## Gemini Files API

| Request | Answer |
|---|---|
| `POST /upload/v1beta/files`, `X-Goog-Upload-Command: start` | `200`, header `x-goog-upload-url: https://generativelanguage.googleapis.com/upload/v1beta/files?upload_id={id}` |
| `POST` that URL, `X-Goog-Upload-Command: upload, finalize` | `200` `{"file":{"name":"files/{id}","displayName","mimeType","sizeBytes","uri","state":"PROCESSING"}}`; the bytes are counted, never kept |
| `GET /v1beta/files/{id}` | the file; `state` `PROCESSING` on the first read, `ACTIVE` afterwards (`FAILED` by scenario) |
| `DELETE /v1beta/files/{id}` | `200` `{}` |

- An unknown or deleted file answers `404`.
- A `streamGenerateContent` call naming a file whose last poll did not report `ACTIVE`, or that the mock does
  not hold, answers `400` `File {uri} is not in an ACTIVE state and usage is not allowed.`
- Files live in the memory of `serve`: a restart forgets them.
- Each request is a line of `calls.jsonl` with `"ai":"gemini-files"`, the URL and key facts, and an `action`:
  `start` (`displayName`, `mimeType`, `declaredBytes`, `protocol`, `scenario`), `upload` (`file`, `bytes`,
  `command`, `offset`), `poll` (`file`, `state`) or `delete` (`file`, `isKnownFile`). Model calls keep
  `"ai":"gemini"`, so counting them is unchanged.

## Run

From `api/` (the proxy uses the API's `certifi`):

```bash
uv run python ../tools/mock-ai/mock_ai.py serve
```

It writes a certificate for both vendor hosts, a CA bundle (certifi + that certificate), a placeholder
whisper model, and `mock-ai.env` with the variables the API needs. Start the test API with them:

```bash
env $(cat /path/from/the/log/mock-ai.env | xargs) APP_ENV=test uv run uvicorn app.main:app --port 5070
```

Then in `/settings?tab=general` save any key on the Google AI and OpenAI sub-tabs — the fake keys of the test
cases work, since the mock never checks them. Claude CLI reads `Signed in`.

| Option | Default | Meaning |
|---|---|---|
| `--state-dir` | `{tmp}/video-tool-mock-ai`, or `MOCK_AI_STATE_DIR` | certificate, bundle, `calls.jsonl`, scenario |
| `serve --port` | `5077` | the proxy |

`serve` clears the calls log and the scenario when it starts.

## Scenarios

A scenario is a JSON list of rules. Each call takes the first rule that matches it and has uses left:

```bash
uv run python ../tools/mock-ai/mock_ai.py scenario '[{"ai":"gemini","status":429,"error":"Resource has been exhausted","times":1}]'
uv run python ../tools/mock-ai/mock_ai.py scenario '[{"ai":"gemini","upload":"FAILED","times":1}]'
uv run python ../tools/mock-ai/mock_ai.py scenario '[{"ai":"gemini","upload":"error","status":503,"error":"Upload unavailable","match":"part-02"}]'
uv run python ../tools/mock-ai/mock_ai.py scenario '[]'
uv run python ../tools/mock-ai/mock_ai.py clear
```

| Key | Meaning |
|---|---|
| `ai` | `claude`, `gemini`, `openai`, `whisper` or `claude-auth`. Without it the rule applies to the three prompt models only |
| `upload` | Gemini Files API: the rule applies to uploads only, and a rule without it never does. `FAILED` — the upload succeeds and the file reads `FAILED` instead of `ACTIVE`; `error` — the `start` request answers `status` (default `500`) with `error`. One use per upload |
| `match` | text that must appear in the instructions or the message, e.g. `runs from 01:40` for the second window; for an `upload` rule, in the upload's display name or MIME type, e.g. `part-02` |
| `times` | how many calls the rule applies to; unlimited without it |
| `text` / `reply` / `chunks` | answer with this raw text, this JSON object, or these stream chunks in order |
| `silent_sec` | wait this long before the first byte or line; for an `upload` rule, before answering `start` |
| `chunk_every_sec` | wait this long between stream chunks |
| `status` + `error` | Gemini / OpenAI: answer this HTTP status with `{"error":{"message":…}}` |
| `block` | Gemini: `promptFeedback.blockReason`, no candidate |
| `finish_reason` | Gemini: the last chunk's `finishReason` (default `STOP`) |
| `fail` | OpenAI: a `response.failed` event; claude: a result event with `is_error` |
| `incomplete` / `refusal` | OpenAI: `response.incomplete` with this reason / a refusal delta |
| `exit` + `stderr` | claude, whisper: exit with this code and stderr |
| `segments` | whisper: `[[start_s, end_s, text], …]`; `[]` for a video with no speech |
| `logged_out` | `claude-auth`: `auth status` reports not signed in |

## Limits

- `HTTPS_PROXY` routes every HTTPS call of the API through the mock; hosts other than the two vendors pass
  through a plain tunnel, so YouTube and the media providers still work in the same run.
- `SSL_CERT_FILE` replaces the CA list of the API's HTTPS calls; the bundle keeps certifi's roots.
- The claude mock runs with whatever `python3` is first on `PATH` (`uv run` puts the API's venv first); it uses
  the standard library only.
- Answers check structure, not wording: they are built from the message, never from the frames.
