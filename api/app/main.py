from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.container import build_container, close_container
from app.logger import configure_logging
from app.modules.ai_models.http_errors import register_ai_model_error_handlers
from app.modules.app_settings.http_errors import register_app_setting_error_handlers
from app.modules.app_settings.router import router as app_settings_router
from app.modules.film_clones.http_errors import register_film_clone_error_handlers
from app.modules.film_clones.router import router as film_clones_router
from app.modules.films.episode_router import router as film_episode_router
from app.modules.films.http_errors import register_film_error_handlers
from app.modules.films.library_router import router as film_library_router
from app.modules.films.project_router import router as film_project_router
from app.modules.films.result_router import router as film_result_router
from app.modules.jobs.http_errors import register_job_error_handlers
from app.modules.jobs.router import router as jobs_router
from app.modules.prompt_presets.http_errors import register_prompt_preset_error_handlers
from app.modules.prompt_presets.router import router as prompt_presets_router
from app.modules.providers.http_errors import register_provider_error_handlers
from app.modules.providers.router import router as providers_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    container = build_container(settings)
    app.state.container = container
    container.prompt_preset_service.ensure_default_preset()
    container.provider_setting_service.ensure_providers()
    container.film_style_service.ensure_builtin_styles()
    container.clone_job_watcher.apply_finished_jobs()
    if settings.batch_enabled:
        container.worker.start()
        container.flow_ws_server.start()
        container.generation_worker.start()
    yield
    close_container(container)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    app = FastAPI(title="Video Tool API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(jobs_router)
    app.include_router(prompt_presets_router)
    app.include_router(app_settings_router)
    app.include_router(providers_router)
    app.include_router(film_clones_router)
    app.include_router(film_project_router)
    app.include_router(film_library_router)
    app.include_router(film_episode_router)
    app.include_router(film_result_router)
    register_job_error_handlers(app)
    register_prompt_preset_error_handlers(app)
    register_app_setting_error_handlers(app)
    register_provider_error_handlers(app)
    register_film_clone_error_handlers(app)
    register_film_error_handlers(app)
    register_ai_model_error_handlers(app)
    return app


app = create_app()
