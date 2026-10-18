# api coding conventions (delta)

Root rules first: [../../docs/coding-conventions.md](../../docs/coding-conventions.md). Python-specific additions:

## Types and data — Critical

- Value objects are `@dataclass(frozen=True)`: `KeyMoment`, `Transcript`, `Command`, `VideoUpload`.
- Enumerations are `StrEnum` stored as their value (`_string_enum` in `models.py`) — never raw strings in code.
  - ✅ `job.status == JobStatus.DONE` ❌ `job.status == "done"`
- Datetimes are timezone-aware UTC (`utc_now()`); columns use `UtcDateTime`.
- A "not found" lookup returns `X | None` only at the repository; the service turns `None` into a domain error.

## FastAPI — Critical

- Dependencies use `Annotated[..., Depends(...)]` (see `JobServiceDependency`); no `Depends()` in defaults.
- Handlers are plain `def` (sync). The repository and `CommandRunner` block, and FastAPI runs sync handlers in its threadpool.
- Response DTOs extend `BaseModel` with `alias_generator=to_camel`; build them with `model_validate(orm_object)`.
- Wire new services in `container.py`; read them through a `get_<service>(request)` dependency.

## Config — Preferred

- Every setting is a typed field on `Settings` with a default that works locally (only `database_url` has none); add it to `.env.example` in the same change.
- Durations end in `_sec` / `_ms`, sizes in `_mb` / `_bytes`.

## Logging — Preferred

- `logger = logging.getLogger(__name__)` per module; log job ids and step names, never transcript text or file contents.
- Use `logger.exception` inside the per-job `except` so the traceback reaches the daily log.
