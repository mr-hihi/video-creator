import re

from app.common.process import CommandError
from app.modules.jobs.errors import InvalidYoutubeJobError, YoutubeUnreachableError
from app.modules.jobs.video_to_markdown.transcript import format_timestamp
from app.modules.jobs.youtube_to_markdown.links import parse_youtube_link, to_watch_url
from app.modules.jobs.youtube_to_markdown.video_info import VideoInfo, info_json_to_video_info
from app.modules.jobs.youtube_to_markdown.ytdlp_downloader import YtDlpDownloader

MS_PER_MINUTE = 60_000
REJECTED_LIVE_STATUSES = frozenset({"is_live", "is_upcoming", "post_live"})
UNREACHABLE_REASON_MARKERS = ("Unable to download", "HTTP Error", "not a bot", "timed out")


class YoutubeVideoChecker:
    def __init__(self, downloader: YtDlpDownloader, max_duration_min: int):
        self._downloader = downloader
        self._max_duration_min = max_duration_min

    def fetch_convertible_video(self, link: str) -> VideoInfo:
        video_id = parse_youtube_link(link)
        video = self._fetch_video_info(video_id)
        if video.live_status in REJECTED_LIVE_STATUSES:
            raise InvalidYoutubeJobError("Live or upcoming videos are not supported")
        if video.duration_ms > self._max_duration_min * MS_PER_MINUTE:
            raise InvalidYoutubeJobError(
                f"Video is {format_timestamp(video.duration_ms)} long; "
                f"the limit is {self._max_duration_min} min"
            )
        return video

    def _fetch_video_info(self, video_id: str) -> VideoInfo:
        try:
            info = self._downloader.read_video_info(to_watch_url(video_id))
        except CommandError as error:
            raise ytdlp_failure_to_error(error, video_id) from error
        return info_json_to_video_info(info)


def ytdlp_failure_to_error(
    error: CommandError, video_id: str
) -> InvalidYoutubeJobError | YoutubeUnreachableError:
    reasons = re.findall(rf"ERROR: \[youtube\] {re.escape(video_id)}: ([^\n]+)", str(error))
    if reasons and not _is_unreachable_reason(reasons[-1]):
        return InvalidYoutubeJobError(f"YouTube refused the video: {reasons[-1].strip()}")
    return YoutubeUnreachableError(f"Could not reach YouTube: {error}")


def _is_unreachable_reason(reason: str) -> bool:
    return any(marker in reason for marker in UNREACHABLE_REASON_MARKERS)
