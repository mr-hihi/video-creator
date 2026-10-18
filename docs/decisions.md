# Workspace decisions

Package-level ADRs: [api](../api/docs/decisions.md) · [frontend](../frontend/docs/decisions.md).

## W1 — Polyglot monorepo orchestrated by `run.sh`

- **Decision:** `api/` (Python) and `frontend/` (Node) sit side by side with no JS workspace manager; `run.sh` starts, tests and migrates both.
- **Why:** the two runtimes share no package manager, so nx / turbo would add a layer with nothing to cache.
- **Guardrail:** add a workspace command to `run.sh`, not a root `package.json`.

## W2 — Frontend + API only; no admin app, no RBAC, no Redis

- **Decision:** the `pj-init` admin app, RBAC tables and Redis were left out at scaffold time (2026-09-27).
- **Why:** single-user local tool; the job queue lives in MySQL (see api ADR A1).
- **Guardrail:** do not add auth or a queue broker without a stated multi-user or throughput need.

## W3 — One captcha adapter chosen by env

- **Decision:** the upload is protected by a captcha whose provider (`turnstile` / `recaptcha` / `hcaptcha`) is set by `CAPTCHA_PROVIDER` / `NEXT_PUBLIC_CAPTCHA_PROVIDER`.
- **Why:** every provider verifies with the same `{secret, response} → {success}` shape, so switching is an env change.
- **Guardrail:** never branch on provider outside `api/app/common/captcha.py` and `frontend/src/lib/captcha/`.
- **Local switch:** `CAPTCHA_ENABLED=false` (api) and `NEXT_PUBLIC_CAPTCHA_ENABLED=false` (frontend) turn the captcha off; both default to `true` and are `false` only in the ignored local / test env files. Turn off both sides together — the frontend alone gets 403, the api alone shows a widget nobody needs.

## W4 — Fixed port block

- **Decision:** dev 4020–4029, test 5070–5079 (recorded in the port-allocator inventory).
- **Why:** every local project owns one 10-port block, so stacks run side by side. The first free test block, 5060–5069, cannot hold an api/frontend pair: 5060 and 5061 are SIP ports that Chromium blocks and Next.js refuses (`Bad port: "5061" is reserved for sips`).
- **Guardrail:** new services take the next free digit in the block (`x2`…`x9`), never a random port.
