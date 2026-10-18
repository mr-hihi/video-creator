# Template — job type handler

```
app/modules/jobs/<job_type>/
├── handler.py        # orchestrates steps, reports progress
├── <tool>_<role>.py  # adapter over CommandRunner (one per external program)
└── <logic>.py        # pure functions, no I/O
```

```python
# <tool>_<role>.py
@dataclass(frozen=True)
class FfmpegConfig:
    ffmpeg_bin: str
    ffprobe_bin: str
    timeout_sec: float


class FfmpegClipCutter:
    def __init__(self, config: FfmpegConfig, runner: CommandRunner):
        self._config = config
        self._runner = runner

    def cut(self, video_path: Path, clip: ClipRange, output_path: Path) -> Path:
        self._runner.run(
            Command(
                args=[self._config.ffmpeg_bin, "-y", "-ss", clip.start_text, "-to", clip.end_text,
                      "-i", str(video_path), "-c", "copy", str(output_path)],
                timeout_sec=self._config.timeout_sec,
            )
        )
        return output_path


# handler.py
class TrimVideoHandler:
    def __init__(self, storage: JobStorage, cutter: FfmpegClipCutter):
        self._storage = storage
        self._cutter = cutter

    def handle(self, job: Job, report_step: Callable[[JobStep], None]) -> None:
        self._storage.create_processing_dirs(job.id)
        report_step(JobStep.CUTTING_CLIP)
        clip = to_clip_range(job.options)
        output_path = self._storage.output_dir(job.id) / "clip.mp4"
        self._cutter.cut(self._storage.source_path(job.id, job.source_filename), clip, output_path)
        self._storage.write_archive(job.id)


# container.py
BatchWorker(repository, {..., JobType.TRIM_VIDEO: TrimVideoHandler(storage, cutter)}, ...)
```

- Raise on failure; the worker records `failed` with `str(error)`.
- The shutdown path is already handled by the worker (A2) — do not catch `CommandError` to "retry".
