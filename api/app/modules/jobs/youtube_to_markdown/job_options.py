from typing import Any

from app.modules.jobs.youtube_to_markdown.links import to_watch_url

URL_KEY = "url"
VIDEO_ID_KEY = "videoId"
LANGUAGE_KEY = "language"
CAPTION_KIND_KEY = "captionKind"


def build_youtube_job_options(video_id: str, language: str) -> dict[str, Any]:
    return {URL_KEY: to_watch_url(video_id), VIDEO_ID_KEY: video_id, LANGUAGE_KEY: language}
