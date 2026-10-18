from dataclasses import dataclass
from pathlib import Path

from app.modules.films.errors import FilmConflictError, FilmFileNotFoundError
from app.modules.films.film_access import FilmAccess
from app.modules.films.film_files import FilmFiles
from app.modules.films.film_outputs import (
    FilmOutput,
    build_output_file_name,
    get_stored_output_path,
)

NO_OUTPUT_MESSAGE = "Episode {number} has no {output} yet"


@dataclass(frozen=True)
class EpisodeDownload:
    path: Path
    file_name: str


class FilmResultFiles:
    def __init__(self, access: FilmAccess, files: FilmFiles):
        self._access = access
        self._files = files

    def get_download(self, episode_id: str, output: FilmOutput) -> EpisodeDownload:
        context = self._access.get_episode(episode_id)
        no_output_error = FilmConflictError(
            NO_OUTPUT_MESSAGE.format(number=context.episode.number, output=output.value)
        )
        stored_path = get_stored_output_path(context.episode, output)
        if stored_path is None:
            raise no_output_error
        try:
            file_path = self._files.resolve_existing(stored_path)
        except FilmFileNotFoundError as error:
            raise no_output_error from error
        return EpisodeDownload(path=file_path, file_name=build_output_file_name(context, output))

    def resolve_preview(self, relative_path: str) -> Path:
        return self._files.resolve_existing(relative_path)
