# Workflow — adding a new job type

Template: [template-worker-batch.md](../templates/template-worker-batch.md).

1. Add the value to `JobType` (and new `JobStep` values) in `app/modules/jobs/models.py`. No migration is needed — the columns are `VARCHAR`.
2. Create `app/modules/jobs/<job_type>/` with `handler.py` + its pure-logic modules + adapters over `CommandRunner`.
3. Register the handler in `container.py` inside the `BatchWorker(... {JobType.X: handler})` map.
4. Add `JobService.create_<job_type>_job(...)` (validate → save source → `repository.add` → `notify_worker()`), then a route — follow [workflow-implementing-a-new-api-endpoint.md](workflow-implementing-a-new-api-endpoint.md).
5. Put job-specific input in `Job.options` (JSON); read it in the handler with a default.
6. Make `JobService.get_job_detail` type-aware: today it reads `<name>.md` for every `done` job, so a type without a `.md` answers 500 on `GET /jobs/{id}`.
7. Tests: handler with mocked adapters + real `JobStorage(tmp_path)`; pure logic directly; every branch.
8. Frontend: add the type to the `Job` union and `JobStep` in `features/jobs/types.ts`; add its step list to `JOB_STEPS_BY_TYPE`, its labels to `JOB_STEP_LABELS` and its badge to `JOB_SOURCE_LABELS` in `features/jobs/constants.ts`.

- **Critical** — the handler raises on failure; the worker marks the job `failed`. Never catch-and-swallow inside the handler.
- **Critical** — call `report_step(JobStep.X)` before each long step so the UI shows progress.
