# Workflow — debugging the frontend

| Symptom | Check | Fix |
| --- | --- | --- |
| "Could not reach http://localhost:4020" | `curl -s localhost:4020/jobs` | ask the user to start the API (`sh run.sh start`) |
| CORS error in the console | api `CORS_ORIGINS` in `api/.env` / `.env.test` | include the frontend origin (`http://localhost:4021` / `5071`) |
| Upload answers 403 | captcha keys | frontend site key and api secret must be the same provider's pair (test keys locally) |
| Images missing in preview | network tab for `/jobs/{id}/files/images/…` | job not `done` (409) or path not relative |
| Stale UI after env change | `.next/` | env is inlined at build: restart `next dev` / rebuild; delete `.next/` if needed |
| Next API mismatch / deprecation | `node_modules/next/dist/docs/` | follow the bundled guide, not memory |
