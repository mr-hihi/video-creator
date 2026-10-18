import re
from urllib.parse import SplitResult, parse_qs, urlsplit

from app.modules.jobs.errors import InvalidYoutubeJobError

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
SCHEME_PATTERN = re.compile(r"^[a-z][a-z\d+.-]*://", re.IGNORECASE)
ACCEPTED_SCHEMES = frozenset({"http", "https"})
DEFAULT_SCHEME_PREFIX = "https://"
WATCH_HOSTS = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com"})
SHORT_LINK_HOST = "youtu.be"
WATCH_PATH = "/watch"
VIDEO_ID_PATH_PREFIXES = frozenset({"shorts", "live", "embed"})
VIDEO_ID_QUERY_KEY = "v"
PLAYLIST_QUERY_KEY = "list"
WATCH_URL_PREFIX = "https://www.youtube.com/watch?v="
MS_PER_SECOND = 1000

NOT_A_VIDEO_LINK_MESSAGE = "Not a YouTube video link"
PLAYLIST_LINK_MESSAGE = "Playlist links are not supported. Open one video and copy its link"


def parse_youtube_link(link: str) -> str:
    parts = urlsplit(_with_scheme(link.strip()))
    host = (parts.hostname or "").lower()
    video_id = _find_video_id(host, parts)
    if VIDEO_ID_PATTERN.match(video_id):
        return video_id
    if _is_playlist_link(host, parts):
        raise InvalidYoutubeJobError(PLAYLIST_LINK_MESSAGE)
    raise InvalidYoutubeJobError(NOT_A_VIDEO_LINK_MESSAGE)


def to_watch_url(video_id: str) -> str:
    return f"{WATCH_URL_PREFIX}{video_id}"


def to_timestamp_url(video_id: str, at_ms: int) -> str:
    return f"{to_watch_url(video_id)}&t={at_ms // MS_PER_SECOND}s"


def _with_scheme(link: str) -> str:
    return link if SCHEME_PATTERN.match(link) else f"{DEFAULT_SCHEME_PREFIX}{link}"


def _find_video_id(host: str, parts: SplitResult) -> str:
    if parts.scheme.lower() not in ACCEPTED_SCHEMES:
        return ""
    path_segments = [segment for segment in parts.path.split("/") if segment]
    if host == SHORT_LINK_HOST:
        return path_segments[0] if len(path_segments) == 1 else ""
    if host not in WATCH_HOSTS:
        return ""
    if parts.path == WATCH_PATH:
        return parse_qs(parts.query).get(VIDEO_ID_QUERY_KEY, [""])[0]
    if len(path_segments) == 2 and path_segments[0] in VIDEO_ID_PATH_PREFIXES:
        return path_segments[1]
    return ""


def _is_playlist_link(host: str, parts: SplitResult) -> bool:
    return host in WATCH_HOSTS and PLAYLIST_QUERY_KEY in parse_qs(parts.query)
