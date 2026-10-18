from pathlib import Path

from app.common.process import CommandError
from app.modules.jobs.storage import JobStorage
from app.modules.jobs.video_to_markdown.ffmpeg_media import FfmpegMediaProcessor, FrameSampling
from app.modules.jobs.video_to_markdown.moment_windows import MS_PER_SECOND, SampleFrame
from app.modules.jobs.video_to_markdown.moments import FRAME_END_MARGIN_MS

SAMPLE_PREFIX = "sample-"
SAMPLE_OUTPUT_PATTERN = f"{SAMPLE_PREFIX}%05d.jpg"
SAMPLE_GLOB = f"{SAMPLE_PREFIX}*.jpg"


class FrameSamplingError(Exception):
    pass


class FrameSampler:
    def __init__(self, storage: JobStorage, media: FfmpegMediaProcessor, max_width_px: int):
        self._storage = storage
        self._media = media
        self._max_width_px = max_width_px

    def sample(self, job_id: str, video_path: Path, duration_ms: int) -> list[SampleFrame]:
        samples_dir = self._storage.samples_dir(job_id)
        self._storage.delete_samples(job_id)
        samples_dir.mkdir(parents=True)
        frame_count = to_sample_count(duration_ms)
        if frame_count:
            self._run_sampling(
                FrameSampling(
                    video_path=video_path,
                    output_pattern=samples_dir / SAMPLE_OUTPUT_PATTERN,
                    frame_count=frame_count,
                    max_width_px=self._max_width_px,
                )
            )
        return [path_to_sample_frame(path) for path in sorted(samples_dir.glob(SAMPLE_GLOB))]

    def delete_samples(self, job_id: str) -> None:
        self._storage.delete_samples(job_id)

    def _run_sampling(self, sampling: FrameSampling) -> None:
        try:
            self._media.sample_frames(sampling)
        except CommandError as error:
            raise FrameSamplingError(f"Frame sampling failed: {error}") from error


def to_sample_count(duration_ms: int) -> int:
    if duration_ms < FRAME_END_MARGIN_MS:
        return 0
    return (duration_ms - FRAME_END_MARGIN_MS) // MS_PER_SECOND + 1


def path_to_sample_frame(path: Path) -> SampleFrame:
    second = int(path.stem.removeprefix(SAMPLE_PREFIX))
    return SampleFrame(at_ms=second * MS_PER_SECOND, path=path)
