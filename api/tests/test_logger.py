import logging
from datetime import date

import pytest

from app.config import Settings
from app.logger import DailyFileHandler, configure_logging


def build_record(message: str) -> logging.LogRecord:
    return logging.LogRecord("test", logging.INFO, __file__, 1, message, None, None)


@pytest.fixture
def log_dir_after_day_change(tmp_path, monkeypatch):
    clock = {"today": date(2026, 9, 1)}

    class FakeDate(date):
        @classmethod
        def today(cls):
            return clock["today"]

    monkeypatch.setattr("app.logger.date", FakeDate)
    (tmp_path / "app-2026-07-01.log").write_text("expired")
    (tmp_path / "app-2026-08-20.log").write_text("recent")
    handler = DailyFileHandler(tmp_path, retention_days=30)
    handler.emit(build_record("first day"))
    clock["today"] = date(2026, 9, 2)
    handler.emit(build_record("second day"))
    handler.close()
    return tmp_path


@pytest.fixture
def log_file_names(log_dir_after_day_change):
    return sorted(path.name for path in log_dir_after_day_change.iterdir())


@pytest.fixture
def second_day_log(log_dir_after_day_change):
    return (log_dir_after_day_change / "app-2026-09-02.log").read_text()


@pytest.fixture
def root_handler_types(tmp_path, request):
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    configure_logging(
        Settings(database_url="sqlite://", log_driver=request.param, log_dir=tmp_path)
    )
    handler_types = [type(handler) for handler in root_logger.handlers]
    for handler in root_logger.handlers:
        handler.close()
    root_logger.handlers = original_handlers
    return handler_types


def test_daily_file_handler_deletes_files_past_retention(log_file_names):
    assert log_file_names == ["app-2026-08-20.log", "app-2026-09-01.log", "app-2026-09-02.log"]


def test_daily_file_handler_writes_to_the_new_day_file(second_day_log):
    assert second_day_log.strip() == "second day"


@pytest.mark.parametrize("root_handler_types", ["file"], indirect=True)
def test_configure_logging_adds_daily_file_for_file_driver(root_handler_types):
    assert root_handler_types == [logging.StreamHandler, DailyFileHandler]


@pytest.mark.parametrize("root_handler_types", ["stdout"], indirect=True)
def test_configure_logging_logs_to_console_only_for_other_drivers(root_handler_types):
    assert root_handler_types == [logging.StreamHandler]
