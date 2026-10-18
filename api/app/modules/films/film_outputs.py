from enum import StrEnum

from app.modules.films.film_access import EpisodeContext
from app.modules.films.film_files import build_episode_stem
from app.modules.films.models import Episode


class FilmOutput(StrEnum):
    VIDEO = "video"
    SUBTITLES = "subtitles"
    THUMBNAIL = "thumbnail"


FILE_SUFFIXES_BY_OUTPUT = {
    FilmOutput.VIDEO: ".mp4",
    FilmOutput.SUBTITLES: ".srt",
    FilmOutput.THUMBNAIL: "-thumbnail.jpg",
}
STORED_PATH_FIELDS_BY_OUTPUT = {
    FilmOutput.VIDEO: "video_path",
    FilmOutput.SUBTITLES: "subtitles_path",
    FilmOutput.THUMBNAIL: "thumbnail_path",
}


def build_output_file_name(context: EpisodeContext, output: FilmOutput) -> str:
    episode = context.episode
    stem = build_episode_stem(context.project.name, episode.number, episode.title)
    return f"{stem}{FILE_SUFFIXES_BY_OUTPUT[output]}"


def get_stored_output_path(episode: Episode, output: FilmOutput) -> str | None:
    return getattr(episode, STORED_PATH_FIELDS_BY_OUTPUT[output])
