import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_ENV = os.getenv("APP_ENV", "local")

CaptchaProvider = Literal["turnstile", "recaptcha", "hcaptcha"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", f".env.{APP_ENV}"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = APP_ENV
    database_url: str
    cors_origins: list[str] = ["http://localhost:4021"]

    log_driver: str = "file"
    log_dir: Path = Path("logs")
    log_retention_days: int = 30

    captcha_enabled: bool = True
    captcha_provider: CaptchaProvider = "turnstile"
    captcha_secret: str = ""

    storage_dir: Path = Path("storage")
    max_upload_mb: int = 4096

    batch_enabled: bool = True
    batch_poll_interval_sec: float = 5.0

    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    media_timeout_sec: int = 1800

    whisper_bin: str = "whisper-cli"
    whisper_model_path: Path = Path("models/ggml-large-v3-turbo.bin")
    whisper_timeout_sec: int = 7200

    claude_bin: str = "claude"
    ai_image_max_side_px: int = 480
    ai_image_jpeg_quality: int = 60
    ai_moments_timeout_sec: int = 600
    max_moments: int = 12
    claude_max_images_per_call: int = 100
    gemini_max_images_per_call: int = 300
    openai_max_images_per_call: int = 300
    sample_frame_width: int = 512

    ytdlp_bin: str = "yt-dlp"
    youtube_max_duration_min: int = 180
    youtube_video_height: int = 720
    youtube_timeout_sec: int = 1800

    film_scene_threshold: float = 0.4
    film_scene_timeout_sec: int = 3600
    film_prompt_timeout_sec: int = 900
    clone_ai_silence_sec: float = 900
    clone_ai_max_run_sec: int = 3600
    clone_script_shots_per_call: int = 100

    film_worker_poll_interval_sec: float = 5.0
    film_request_max_attempts: int = 5
    film_script_timeout_sec: int = 600
    film_assembly_timeout_sec: int = 3600
    film_music_volume: float = 0.2
    film_upload_max_mb: int = 20

    settings_secret_key: str = ""
    provider_test_timeout_sec: float = 15.0
    flow_ws_port: int = 4024
    local_server_timeout_sec: float = 1800.0
    sd_denoising_strength: float = 0.6
    sd_composite_denoising_strength: float = 0.75


@lru_cache
def get_settings() -> Settings:
    return Settings()
