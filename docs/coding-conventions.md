# Coding conventions (shared)

Packages add only their delta: [api](../api/docs/coding-conventions.md) · [frontend](../frontend/docs/coding-conventions.md).

## Naming — Critical

| Kind | Rule | Good | Bad |
| --- | --- | --- | --- |
| Boolean | `is` / `has` / `can` / `should` prefix (settings mirror their env key, e.g. `batch_enabled`) | `isJobInProgress`, `_is_speech` | `jobProgress`, `speech` |
| Collection | plural | `captured_moments`, `jobs` | `moment_list` |
| Function | verb + noun, says what comes back | `find_recent`, `buildJobFileUrl` | `recent`, `jobUrl` |
| Units | carry the unit | `timeout_sec`, `at_ms`, `pollIntervalMs` | `timeout`, `at` |
| Constant | `UPPER_SNAKE_CASE`, named after its meaning | `MIN_MOMENT_GAP_MS` | `GAP`, a bare `3000` |
| Map | `xByY` / `x_by_y` | `handlers_by_type` | `handler_map` |
| Transform | input + `To` + output | `whisper_json_to_transcript` | `parse_whisper` |
| Adapter | vendor + role | `FfmpegMediaProcessor`, `WhisperCppTranscriber` | `MediaHelper` |

- **Critical** — no magic values: a literal that carries meaning gets a named constant.
- **Preferred** — no vendor name unless the code exists because of that vendor.

## Functions — Preferred

- One thing per function, one level of abstraction; split past ~40 lines.
- Guard clauses first, main path unindented; at most two levels of nesting.
- 0–2 parameters; 4+ → a named dataclass / interface (`Command`, `VideoUpload`, `MarkdownSource`).
- No flag arguments — expose two functions instead.

## Comments — Critical

- Ship code with **no comments**. The only exception is a hidden constraint the reader would otherwise "fix", in one English line.
  - ✅ `# MySQL DATETIME drops the offset, so values are stored as naive UTC and re-tagged on read.`
  - ❌ `# get the job by id`
- Never a comment inside JSX. Name the value or extract a component instead.
- Rationale goes to `decisions.md` and the commit message, never into code.

## Errors — Critical

- Raise a domain error type (`JobNotFoundError`, `CommandError`) from business code and turn it into a transport error at the edge only (api: one `http_errors.py` table per module; frontend: `ApiError`).
- Wrap every external tool / SDK in one adapter that converts its failures into the codebase's error type.
- Inside a batch loop, one job's failure marks that job `failed` and the loop continues.

## Git

- Commit only when the user asks. Stage with explicit paths — never `git commit -a`.
