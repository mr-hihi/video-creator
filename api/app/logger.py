import logging
from datetime import date, timedelta
from pathlib import Path

from app.config import Settings

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
FILE_LOG_DRIVER = "file"


class DailyFileHandler(logging.FileHandler):
    def __init__(self, log_dir: Path, retention_days: int):
        self._log_dir = log_dir
        self._retention_days = retention_days
        self._current_date = date.today()
        log_dir.mkdir(parents=True, exist_ok=True)
        super().__init__(self._path_for(self._current_date), encoding="utf-8", delay=True)

    def emit(self, record: logging.LogRecord) -> None:
        today = date.today()
        if today != self._current_date:
            self._switch_to(today)
        super().emit(record)

    def _path_for(self, day: date) -> Path:
        return self._log_dir / f"app-{day.isoformat()}.log"

    def _switch_to(self, day: date) -> None:
        self.close()
        self._current_date = day
        self.baseFilename = str(self._path_for(day).resolve())
        self._delete_expired_files(day)

    def _delete_expired_files(self, today: date) -> None:
        oldest_kept = today - timedelta(days=self._retention_days)
        for log_file in self._log_dir.glob("app-*.log"):
            if log_file.stem.removeprefix("app-") < oldest_kept.isoformat():
                log_file.unlink(missing_ok=True)


def configure_logging(settings: Settings) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if settings.log_driver == FILE_LOG_DRIVER:
        handlers.append(DailyFileHandler(settings.log_dir, settings.log_retention_days))
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, handlers=handlers, force=True)
