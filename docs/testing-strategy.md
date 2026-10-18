# Testing strategy (workspace)

| Layer | Where | DB? | Command |
| --- | --- | --- | --- |
| API unit (services, adapters, worker, HTTP layer) | `api/tests/` | **Never** — mocks only | `sh run.sh test` |
| Frontend checks | `frontend/` | — | `npm run lint && npm run build` |
| E2E (future) | fenced test stack | `video_tool_test` only | `sh run.sh start_test` |

## Rules

- **Critical** — the test stack uses its own DB (`video_tool_test`), storage (`api/storage-test/`) and ports (5070/5071). Never point it at dev data.
- Known gap: the api repository has no automated test yet — see [api testing strategy](../api/docs/testing-strategy.md).

Package detail: [api](../api/docs/testing-strategy.md) · [frontend](../frontend/docs/testing-strategy.md).
