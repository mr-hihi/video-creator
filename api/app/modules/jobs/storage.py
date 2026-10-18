import shutil
import zipfile
from pathlib import Path
from typing import BinaryIO

from app.common.filenames import to_safe_file_stem

COPY_CHUNK_BYTES = 1024 * 1024
FALLBACK_STEM = "video"
IMAGES_DIR_NAME = "images"
SAMPLES_DIR_NAME = "samples"


class UploadTooLargeError(Exception):
    pass


def to_safe_stem(source_filename: str) -> str:
    return to_safe_file_stem(Path(source_filename).stem, FALLBACK_STEM)


class JobStorage:
    def __init__(self, root_dir: Path, max_upload_bytes: int):
        self._root_dir = root_dir
        self._max_upload_bytes = max_upload_bytes

    def job_dir(self, job_id: str) -> Path:
        return self._root_dir / job_id

    def source_path(self, job_id: str, source_filename: str) -> Path:
        return self.job_dir(job_id) / f"source{Path(source_filename).suffix.lower()}"

    def work_dir(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "work"

    def output_dir(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "output"

    def images_dir(self, job_id: str) -> Path:
        return self.output_dir(job_id) / IMAGES_DIR_NAME

    def samples_dir(self, job_id: str) -> Path:
        return self.job_dir(job_id) / SAMPLES_DIR_NAME

    def markdown_path(self, job_id: str, source_filename: str) -> Path:
        return self.output_dir(job_id) / f"{to_safe_stem(source_filename)}.md"

    def archive_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "result.zip"

    def create_processing_dirs(self, job_id: str) -> None:
        self.work_dir(job_id).mkdir(parents=True, exist_ok=True)
        self.images_dir(job_id).mkdir(parents=True, exist_ok=True)

    def save_source(self, job_id: str, source_filename: str, stream: BinaryIO) -> Path:
        destination = self.source_path(job_id, source_filename)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._copy_limited(stream, destination)
        except UploadTooLargeError:
            shutil.rmtree(self.job_dir(job_id), ignore_errors=True)
            raise
        return destination

    def save_result(self, job_id: str, source_filename: str, markdown: str) -> None:
        self.markdown_path(job_id, source_filename).write_text(markdown, encoding="utf-8")
        self.write_archive(job_id)

    def copy_images(self, source_job_id: str, target_job_id: str) -> None:
        shutil.copytree(self.images_dir(source_job_id), self.images_dir(target_job_id))

    def delete_samples(self, job_id: str) -> None:
        shutil.rmtree(self.samples_dir(job_id), ignore_errors=True)

    def delete_job_files(self, job_id: str) -> None:
        shutil.rmtree(self.job_dir(job_id), ignore_errors=True)

    def write_archive(self, job_id: str) -> Path:
        output_dir = self.output_dir(job_id)
        archive = self.archive_path(job_id)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in sorted(output_dir.rglob("*")):
                if file_path.is_file():
                    zip_file.write(file_path, file_path.relative_to(output_dir))
        return archive

    def _copy_limited(self, stream: BinaryIO, destination: Path) -> None:
        copied_bytes = 0
        with destination.open("wb") as target:
            while chunk := stream.read(COPY_CHUNK_BYTES):
                copied_bytes += len(chunk)
                if copied_bytes > self._max_upload_bytes:
                    raise UploadTooLargeError(
                        f"Upload exceeds the {self._max_upload_bytes} byte limit"
                    )
                target.write(chunk)
