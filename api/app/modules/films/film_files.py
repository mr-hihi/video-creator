import shutil
from pathlib import Path
from typing import BinaryIO

from app.common.filenames import to_safe_file_stem
from app.modules.films.errors import FilmFileNotFoundError, FilmFileTooLargeError
from app.modules.media_generation.clip_segments import CLIP_SEGMENTS_DIR_NAME

FILMS_DIR_NAME = "films"
PROJECTS_DIR_NAME = "projects"
EPISODES_DIR_NAME = "episodes"
SCENES_DIR_NAME = "scenes"
SOURCE_DIR_NAME = "source"
OUTPUT_DIR_NAME = "output"
CHARACTERS_DIR_NAME = "characters"
VOICES_DIR_NAME = "voices"
SCENE_IMAGE_STEM = "image"
SCENE_CLIP_STEM = "clip"
SCENE_NARRATION_STEM = "narration"
MUSIC_STEM = "music"
REFERENCE_STEM = "reference"
VOICE_SAMPLE_STEM = "sample"
VOICE_CONSENT_STEM = "consent"
THUMBNAIL_CANDIDATE_STEM = "thumbnail-candidate-{candidate}"
FALLBACK_EPISODE_STEM = "episode"
EPISODE_STEM = "{project_name} - E{number:02d} - {title}"
COPY_CHUNK_BYTES = 1024 * 1024
BYTES_PER_MB = 1024 * 1024


def build_episode_stem(project_name: str, number: int, title: str) -> str:
    stem = EPISODE_STEM.format(project_name=project_name, number=number, title=title)
    return to_safe_file_stem(stem, FALLBACK_EPISODE_STEM)


class FilmFiles:
    def __init__(self, storage_dir: Path, max_upload_mb: int):
        self._root_dir = storage_dir.resolve() / FILMS_DIR_NAME
        self._max_upload_mb = max_upload_mb

    @property
    def max_upload_mb(self) -> int:
        return self._max_upload_mb

    def project_dir(self, project_id: str) -> Path:
        return self._root_dir / PROJECTS_DIR_NAME / project_id

    def episode_dir(self, project_id: str, episode_id: str) -> Path:
        return self.project_dir(project_id) / EPISODES_DIR_NAME / episode_id

    def source_dir(self, project_id: str, episode_id: str) -> Path:
        return self.episode_dir(project_id, episode_id) / SOURCE_DIR_NAME

    def output_dir(self, project_id: str, episode_id: str) -> Path:
        return self.episode_dir(project_id, episode_id) / OUTPUT_DIR_NAME

    def scene_dir(self, project_id: str, episode_id: str, scene_id: str) -> Path:
        return self.episode_dir(project_id, episode_id) / SCENES_DIR_NAME / scene_id

    def scene_image_path(
        self, project_id: str, episode_id: str, scene_id: str, file_extension: str
    ) -> Path:
        scene_dir = self.scene_dir(project_id, episode_id, scene_id)
        return scene_dir / f"{SCENE_IMAGE_STEM}.{file_extension}"

    def scene_clip_path(
        self, project_id: str, episode_id: str, scene_id: str, file_extension: str
    ) -> Path:
        scene_dir = self.scene_dir(project_id, episode_id, scene_id)
        return scene_dir / f"{SCENE_CLIP_STEM}.{file_extension}"

    def scene_clip_segments_dir(self, project_id: str, episode_id: str, scene_id: str) -> Path:
        return self.scene_dir(project_id, episode_id, scene_id) / CLIP_SEGMENTS_DIR_NAME

    def scene_narration_path(
        self, project_id: str, episode_id: str, scene_id: str, file_extension: str
    ) -> Path:
        scene_dir = self.scene_dir(project_id, episode_id, scene_id)
        return scene_dir / f"{SCENE_NARRATION_STEM}.{file_extension}"

    def music_path(self, project_id: str, episode_id: str, file_extension: str) -> Path:
        return self.episode_dir(project_id, episode_id) / f"{MUSIC_STEM}.{file_extension}"

    def thumbnail_candidate_path(
        self, project_id: str, episode_id: str, candidate: int, file_extension: str
    ) -> Path:
        file_name = f"{THUMBNAIL_CANDIDATE_STEM.format(candidate=candidate)}.{file_extension}"
        return self.output_dir(project_id, episode_id) / file_name

    def character_dir(self, character_id: str) -> Path:
        return self._root_dir / CHARACTERS_DIR_NAME / character_id

    def character_reference_path(self, character_id: str, file_extension: str) -> Path:
        return self.character_dir(character_id) / f"{REFERENCE_STEM}.{file_extension}"

    def voice_dir(self, voice_id: str) -> Path:
        return self._root_dir / VOICES_DIR_NAME / voice_id

    def voice_sample_path(self, voice_id: str, file_extension: str) -> Path:
        return self.voice_dir(voice_id) / f"{VOICE_SAMPLE_STEM}.{file_extension}"

    def voice_consent_path(self, voice_id: str, file_extension: str) -> Path:
        return self.voice_dir(voice_id) / f"{VOICE_CONSENT_STEM}.{file_extension}"

    def to_relative(self, file_path: Path) -> str:
        return file_path.relative_to(self._root_dir).as_posix()

    def to_absolute(self, relative_path: str) -> Path:
        return self._root_dir / relative_path

    def resolve_existing(self, relative_path: str) -> Path:
        root_dir = self._root_dir.resolve()
        candidate = (root_dir / relative_path).resolve()
        if not candidate.is_relative_to(root_dir) or not candidate.is_file():
            raise FilmFileNotFoundError(relative_path)
        return candidate

    def save_upload(self, stream: BinaryIO, destination: Path, too_large_message: str) -> Path:
        max_bytes = self._max_upload_mb * BYTES_PER_MB
        partial_path = destination.with_name(f"{destination.name}.part")
        partial_path.parent.mkdir(parents=True, exist_ok=True)
        written_bytes = 0
        with partial_path.open("wb") as target:
            while chunk := stream.read(COPY_CHUNK_BYTES):
                written_bytes += len(chunk)
                if written_bytes > max_bytes:
                    target.close()
                    partial_path.unlink(missing_ok=True)
                    raise FilmFileTooLargeError(too_large_message)
                target.write(chunk)
        partial_path.replace(destination)
        self.keep_only(destination)
        return destination

    def copy_into(self, source_path: Path, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination)
        self.keep_only(destination)
        return destination

    def keep_only(self, file_path: Path) -> None:
        for sibling in file_path.parent.glob(f"{file_path.stem}.*"):
            if sibling != file_path and sibling.suffix != ".part":
                sibling.unlink(missing_ok=True)

    def delete(self, relative_path: str | None) -> None:
        if relative_path is not None:
            self.to_absolute(relative_path).unlink(missing_ok=True)

    def delete_dir(self, directory: Path) -> None:
        shutil.rmtree(directory, ignore_errors=True)
