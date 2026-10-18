# frontend decisions

## F1 — Upload through `XMLHttpRequest`, everything else through `fetch`

- **Decision:** `apiUpload` uses XHR; `apiFetch` uses `fetch` with a default timeout.
- **Why:** `fetch` has no upload-progress event, and videos can be gigabytes.
- **Guardrail:** don't "unify" uploads onto `fetch`; keep the 60-minute upload timeout separate from the 15-second request timeout.

## F2 — Poll only while a job is in progress

- **Decision:** `refetchInterval` returns 3 s while any job is `pending` / `processing`, else `false`.
- **Why:** jobs take minutes; idle pages must not hammer the API.
- **Guardrail:** no WebSocket / SSE until the API offers one; no `setInterval`.

## F3 — Relative Markdown image paths rewritten at render time

- **Decision:** the API writes `images/…` in the `.md`; `MarkdownPreview` maps them to `/jobs/{id}/files/…`.
- **Why:** the same `.md` must work inside the downloaded zip.
- **Guardrail:** never ask the API to emit absolute URLs.
- **Guardrail:** never load an absolute image URL from Markdown — Film Analysis results are written by Claude from untrusted video content, and a loaded image URL would send data to another host.

## F4 — Server component page, client organisms

- **Decision:** `app/jobs/[id]/page.tsx` awaits `params` (Next 16 `PageProps`) and hands `jobId` to the client `JobDetailPanel`.
- **Why:** keeps metadata server-side and data fetching in TanStack Query on the client.
- **Guardrail:** don't fetch job data in the server component.
