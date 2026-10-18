from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import mysql, sqlite

from app import main
from app.batch.worker import BatchWorker
from app.common.process import CommandRunner
from app.config import Settings
from app.container import Container, build_container, close_container
from app.db import UtcDateTime, create_session_factory, utc_now
from app.modules.app_settings.ai_model_service import AiModelSettingService
from app.modules.app_settings.service import AppSettingService
from app.modules.film_clones.clone_actions import CloneActionService
from app.modules.film_clones.clone_steps import CloneJobWatcher
from app.modules.film_clones.editing import CloneEditingService
from app.modules.film_clones.service import FilmCloneService
from app.modules.films.character_service import FilmCharacterService
from app.modules.films.episode_service import EpisodeService
from app.modules.films.film_access import FilmAccess
from app.modules.films.project_service import FilmProjectService
from app.modules.films.request_service import FilmRequestService
from app.modules.films.result_files import FilmResultFiles
from app.modules.films.scene_service import SceneService
from app.modules.films.stage_runner import EpisodeStageRunner
from app.modules.films.step_commands import EpisodeStepCommands
from app.modules.films.style_service import FilmStyleService
from app.modules.films.thumbnail_service import FilmThumbnailService
from app.modules.films.voice_service import FilmVoiceService
from app.modules.jobs.film_analysis_service import FilmAnalysisJobService
from app.modules.jobs.service import JobService, YoutubeJobService
from app.modules.media_generation.models import GenerationKind
from app.modules.media_generation.service import GenerationService
from app.modules.media_generation.worker import GenerationWorker
from app.modules.prompt_presets.service import PromptPresetService
from app.modules.providers.flow_extension import FlowExtensionBridge
from app.modules.providers.flow_ws_server import FlowWsServer
from app.modules.providers.service import ProviderSettingService

UTC_PLUS_7 = timezone(timedelta(hours=7))


@pytest.fixture
def utc_type():
    return UtcDateTime()


@pytest.fixture
def bound_value(utc_type):
    return utc_type.process_bind_param(
        datetime(2026, 9, 27, 16, 0, tzinfo=UTC_PLUS_7), mysql.dialect()
    )


@pytest.fixture
def read_value(utc_type):
    return utc_type.process_result_value(datetime(2026, 9, 27, 9, 0), mysql.dialect())


@pytest.fixture
def bound_none(utc_type):
    return utc_type.process_bind_param(None, mysql.dialect())


@pytest.fixture
def read_none(utc_type):
    return utc_type.process_result_value(None, mysql.dialect())


@pytest.fixture
def mysql_column_type(utc_type):
    return utc_type.load_dialect_impl(mysql.dialect())


@pytest.fixture
def sqlite_column_type(utc_type):
    return utc_type.load_dialect_impl(sqlite.dialect())


@pytest.fixture
def session_factory():
    return create_session_factory("sqlite://")


@pytest.fixture
def container():
    return build_container(Settings(database_url="sqlite://"))


@pytest.fixture
def close_calls():
    calls = MagicMock()
    fake_container = Container(
        job_service=MagicMock(spec=JobService),
        youtube_job_service=MagicMock(spec=YoutubeJobService),
        film_analysis_job_service=MagicMock(spec=FilmAnalysisJobService),
        prompt_preset_service=MagicMock(spec=PromptPresetService),
        app_setting_service=MagicMock(spec=AppSettingService),
        ai_model_setting_service=MagicMock(spec=AiModelSettingService),
        provider_setting_service=MagicMock(spec=ProviderSettingService),
        generation_service=MagicMock(spec=GenerationService),
        generation_worker=MagicMock(spec=GenerationWorker),
        flow_extension=MagicMock(spec=FlowExtensionBridge),
        film_clone_service=MagicMock(spec=FilmCloneService),
        clone_action_service=MagicMock(spec=CloneActionService),
        clone_editing_service=MagicMock(spec=CloneEditingService),
        clone_job_watcher=MagicMock(spec=CloneJobWatcher),
        film_project_service=MagicMock(spec=FilmProjectService),
        film_character_service=MagicMock(spec=FilmCharacterService),
        film_style_service=MagicMock(spec=FilmStyleService),
        film_voice_service=MagicMock(spec=FilmVoiceService),
        film_episode_service=MagicMock(spec=EpisodeService),
        film_scene_service=MagicMock(spec=SceneService),
        film_stage_runner=MagicMock(spec=EpisodeStageRunner),
        film_access=MagicMock(spec=FilmAccess),
        film_thumbnail_service=MagicMock(spec=FilmThumbnailService),
        film_result_files=MagicMock(spec=FilmResultFiles),
        film_request_service=MagicMock(spec=FilmRequestService),
        film_step_commands=MagicMock(spec=EpisodeStepCommands),
        flow_ws_server=MagicMock(spec=FlowWsServer),
        captcha_service=MagicMock(),
        worker=MagicMock(spec=BatchWorker),
        command_runner=MagicMock(spec=CommandRunner),
        http_client=MagicMock(spec=httpx.Client),
        provider_http_client=MagicMock(spec=httpx.Client),
    )
    calls.attach_mock(fake_container.worker.stop, "stop")
    calls.attach_mock(fake_container.command_runner.terminate_all, "terminate_all")
    calls.attach_mock(fake_container.film_step_commands.terminate_all, "terminate_film_steps")
    calls.attach_mock(fake_container.worker.wait_until_stopped, "wait_until_stopped")
    calls.attach_mock(fake_container.flow_ws_server.stop, "stop_flow_ws_server")
    calls.attach_mock(fake_container.http_client.close, "close_http_client")
    close_container(fake_container)
    return [call[0] for call in calls.mock_calls]


def run_lifespan(monkeypatch, is_batch_enabled: bool) -> MagicMock:
    fake_container = MagicMock()
    monkeypatch.setattr(main, "build_container", lambda settings: fake_container)
    monkeypatch.setattr(main, "close_container", fake_container.close)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(database_url="sqlite://", batch_enabled=is_batch_enabled),
    )
    with TestClient(main.create_app()):
        pass
    return fake_container


@pytest.fixture
def container_with_batch(monkeypatch):
    return run_lifespan(monkeypatch, is_batch_enabled=True)


@pytest.fixture
def container_without_batch(monkeypatch):
    return run_lifespan(monkeypatch, is_batch_enabled=False)


def test_utc_datetime_stores_naive_utc(bound_value):
    assert bound_value == datetime(2026, 9, 27, 9, 0)


def test_utc_datetime_reads_values_as_utc(read_value):
    assert read_value == datetime(2026, 9, 27, 9, 0, tzinfo=UTC)


def test_utc_datetime_passes_none_through(bound_none, read_none):
    assert bound_none is None
    assert read_none is None


def test_utc_datetime_uses_microsecond_datetime_on_mysql(mysql_column_type):
    assert mysql_column_type.fsp == 6


def test_utc_datetime_uses_plain_datetime_elsewhere(sqlite_column_type):
    assert not hasattr(sqlite_column_type, "fsp")


def test_utc_now_is_timezone_aware():
    assert utc_now().tzinfo is UTC


def test_create_session_factory_binds_the_database_url(session_factory):
    assert str(session_factory.kw["bind"].url) == "sqlite://"


def test_build_container_wires_services(container):
    assert isinstance(container.job_service, JobService)
    assert isinstance(container.youtube_job_service, YoutubeJobService)
    assert isinstance(container.film_analysis_job_service, FilmAnalysisJobService)
    assert isinstance(container.prompt_preset_service, PromptPresetService)
    assert isinstance(container.app_setting_service, AppSettingService)
    assert isinstance(container.ai_model_setting_service, AiModelSettingService)
    assert isinstance(container.worker, BatchWorker)
    assert isinstance(container.film_project_service, FilmProjectService)
    assert isinstance(container.film_episode_service, EpisodeService)
    assert isinstance(container.film_stage_runner, EpisodeStageRunner)
    assert isinstance(container.film_request_service, FilmRequestService)
    assert isinstance(container.film_step_commands, EpisodeStepCommands)
    assert isinstance(container.flow_ws_server, FlowWsServer)


def test_build_container_registers_every_generation_kind(container):
    assert set(container.generation_service._targets_by_kind) == set(GenerationKind)


def test_close_container_stops_worker_before_killing_commands(close_calls):
    assert close_calls == [
        "stop",
        "terminate_all",
        "terminate_film_steps",
        "wait_until_stopped",
        "stop_flow_ws_server",
        "close_http_client",
    ]


def test_lifespan_starts_worker_when_batch_is_enabled(container_with_batch):
    container_with_batch.worker.start.assert_called_once_with()
    container_with_batch.flow_ws_server.start.assert_called_once_with()
    container_with_batch.close.assert_called_once_with(container_with_batch)


def test_lifespan_ensures_the_default_preset(container_with_batch):
    container_with_batch.prompt_preset_service.ensure_default_preset.assert_called_once_with()


def test_lifespan_writes_the_builtin_styles(container_with_batch):
    container_with_batch.film_style_service.ensure_builtin_styles.assert_called_once_with()


def test_lifespan_skips_worker_when_batch_is_disabled(container_without_batch):
    container_without_batch.worker.start.assert_not_called()
    container_without_batch.flow_ws_server.start.assert_not_called()
