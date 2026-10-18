import shutil
from pathlib import Path

from app.modules.film_clones.errors import CloneFileNotFoundError

CLONES_DIR_NAME = "film-clones"
REFERENCES_DIR_NAME = "references"
SCENES_DIR_NAME = "scenes"


class CloneFiles:
    def __init__(self, storage_dir: Path):
        self._root_dir = storage_dir / CLONES_DIR_NAME

    def reference_path(self, clone_id: str, asset_id: str, file_extension: str) -> Path:
        return self._root_dir / clone_id / REFERENCES_DIR_NAME / f"{asset_id}.{file_extension}"

    def scene_path(self, clone_id: str, scene_id: str, file_extension: str) -> Path:
        return self._root_dir / clone_id / SCENES_DIR_NAME / f"{scene_id}.{file_extension}"

    def to_relative(self, file_path: Path) -> str:
        return file_path.relative_to(self._root_dir).as_posix()

    def to_absolute(self, relative_path: str) -> Path:
        return self._root_dir / relative_path

    def resolve_existing(self, relative_path: str) -> Path:
        root_dir = self._root_dir.resolve()
        candidate = (root_dir / relative_path).resolve()
        if not candidate.is_relative_to(root_dir) or not candidate.is_file():
            raise CloneFileNotFoundError(relative_path)
        return candidate

    def keep_only(self, file_path: Path) -> None:
        for sibling in file_path.parent.glob(f"{file_path.stem}.*"):
            if sibling != file_path:
                sibling.unlink(missing_ok=True)

    def delete(self, relative_path: str | None) -> None:
        if relative_path is not None:
            self.to_absolute(relative_path).unlink(missing_ok=True)

    def delete_clone_files(self, clone_id: str) -> None:
        shutil.rmtree(self._root_dir / clone_id, ignore_errors=True)
