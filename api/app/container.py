import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
from sqlalchemy.orm import Session, sessionmaker

from app.batch.worker import BatchWorker, JobHandler
from app.common.captcha import (
    CaptchaVerifier,
    create_captcha_http_client,
    create_captcha_service,
)
from app.common.process import CommandRunner
from app.config import Settings
from app.db import create_session_factory
from app.modules.ai_models.ai_caller import AiCaller
from app.modules.ai_models.ai_calls import AiLimits
from app.modules.ai_models.ai_images import AiImageEncoding
from app.modules.ai_models.claude_cli_client import ClaudeCliClient, ClaudeCliConfig
from app.modules.ai_models.gemini_client import GeminiClient
from app.modules.ai_models.openai_client import OpenAiClient
from app.modules.ai_models.step_models import AiStepModels
from app.modules.ai_models.streamed_answers import AiApiTools
from app.modules.app_settings.ai_model_service import AiModelSettingService, AiModelSettingTools
from app.modules.app_settings.repository import AppSettingRepository
from app.modules.app_settings.service import AppSettingService
from app.modules.film_clones.clone_access import CloneAccess
from app.modules.film_clones.clone_actions import CloneActionService, CloneActionTools
from app.modules.film_clones.clone_activity import AiActivityTracker
from app.modules.film_clones.clone_ai_caller import WatchedCloneAiCaller
from app.modules.film_clones.clone_files import CloneFiles
from app.modules.film_clones.clone_generation import (
    CloneImageQueue,
    CloneReferenceTarget,
    CloneSceneImageTarget,
)
from app.modules.film_clones.clone_steps import (
    CloneFrameSaver,
    CloneJobWatcher,
    CloneReferenceCheck,
    CloneSceneImageCheck,
    CloneStepRunner,
    CloneStepTools,
)
from app.modules.film_clones.editing import CloneEditingService, CloneEditingTools
from app.modules.film_clones.repository import FilmCloneRepository
from app.modules.film_clones.service import FilmCloneService, FilmCloneServiceTools
from app.modules.films.analysis_source import AnalysisSource, AnalysisSourceTools
from app.modules.films.character_service import FilmCharacterService
from app.modules.films.clone_source import CloneSource, CloneSourceTools
from app.modules.films.episode_service import EpisodeService, EpisodeServiceTools
from app.modules.films.ffmpeg_assembler import (
    AssemblerConfig,
    AssemblerTools,
    FfmpegEpisodeAssembler,
)
from app.modules.films.film_access import FilmAccess
from app.modules.films.film_files import FilmFiles
from app.modules.films.film_imports import FilmImports
from app.modules.films.generation_targets import FilmTargetTools, build_film_targets
from app.modules.films.media_queue import FilmMediaQueue
from app.modules.films.project_service import FilmProjectService, FilmProjectTools
from app.modules.films.repository import FilmRepository
from app.modules.films.request_service import FilmRequestService, FilmRequestTools
from app.modules.films.result_files import FilmResultFiles
from app.modules.films.scene_service import SceneService, SceneServiceTools
from app.modules.films.script_writer import EpisodeScriptWriter, ScriptWriterTools
from app.modules.films.stage_runner import EpisodeStageRunner, StageRunnerTools
from app.modules.films.step_commands import EpisodeStepCommands
from app.modules.films.step_worker import EpisodeStepRunner, EpisodeStepTools
from app.modules.films.style_service import FilmStyleService
from app.modules.films.thumbnail_cropper import CropperConfig, FfmpegThumbnailCropper
from app.modules.films.thumbnail_service import FilmThumbnailService, ThumbnailServiceTools
from app.modules.films.voice_service import FilmVoiceService, FilmVoiceTools
from app.modules.jobs.film_analysis.frame_steps import FilmFrameSteps, FilmFrameTools
from app.modules.jobs.film_analysis.handler import (
    FilmAnalysisHandler,
    FilmAnalysisRerunHandler,
    FilmAnalysisTools,
    YoutubeFilmAnalysisHandler,
    YoutubeFilmAnalysisTools,
)
from app.modules.jobs.film_analysis.notes_passes import NotesPasses
from app.modules.jobs.film_analysis.prompt_passes import FilmPromptPasses, PromptPassTools
from app.modules.jobs.film_analysis.scene_detector import FfmpegSceneDetector, SceneDetectorConfig
from app.modules.jobs.film_analysis_service import FilmAnalysisJobService
from app.modules.jobs.job_intake import JobIntake, JobIntakeTools
from app.modules.jobs.models import JobType
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.service import JobService, YoutubeJobService
from app.modules.jobs.storage import JobStorage
from app.modules.jobs.video_to_markdown.ffmpeg_media import FfmpegConfig, FfmpegMediaProcessor
from app.modules.jobs.video_to_markdown.frame_sampler import FrameSampler
from app.modules.jobs.video_to_markdown.handler import VideoToMarkdownHandler, VideoToMarkdownTools
from app.modules.jobs.video_to_markdown.moment_steps import (
    KeyMomentPicker,
    MomentFrameCapturer,
    MomentPickerConfig,
    MomentPickingSteps,
)
from app.modules.jobs.video_to_markdown.whisper_transcriber import (
    WhisperConfig,
    WhisperCppTranscriber,
)
from app.modules.jobs.youtube_to_markdown.handler import (
    YoutubeToMarkdownHandler,
    YoutubeToMarkdownTools,
)
from app.modules.jobs.youtube_to_markdown.transcript_fetcher import YoutubeTranscriptFetcher
from app.modules.jobs.youtube_to_markdown.video_checker import YoutubeVideoChecker
from app.modules.jobs.youtube_to_markdown.ytdlp_downloader import YtDlpConfig, YtDlpDownloader
from app.modules.media_generation.adapters.elevenlabs import ElevenLabsAdapter
from app.modules.media_generation.adapters.fal import FalAdapter
from app.modules.media_generation.adapters.flow_project_owners import (
    FlowProjectOwnerRepositories,
    RepositoryFlowProjectOwners,
)
from app.modules.media_generation.adapters.google_ai import GoogleAiAdapter
from app.modules.media_generation.adapters.google_flow import GoogleFlowAdapter, GoogleFlowTools
from app.modules.media_generation.adapters.local_audio import LocalAudioAdapter
from app.modules.media_generation.adapters.openai_images import OpenAiImageAdapter
from app.modules.media_generation.adapters.replicate import ReplicateAdapter
from app.modules.media_generation.adapters.sd_webui import SdWebUiAdapter, SdWebUiConfig
from app.modules.media_generation.ffmpeg_clip_editor import ClipEditorConfig, FfmpegClipEditor
from app.modules.media_generation.models import GenerationKind
from app.modules.media_generation.provider_adapter import MediaProviderAdapter
from app.modules.media_generation.repository import GenerationRequestRepository
from app.modules.media_generation.service import GenerationService
from app.modules.media_generation.targets import GenerationTarget
from app.modules.media_generation.worker import (
    GenerationWorker,
    GenerationWorkerConfig,
    GenerationWorkerTools,
)
from app.modules.prompt_presets.repository import PromptPresetRepository
from app.modules.prompt_presets.service import PromptPresetService
from app.modules.providers.claude_cli_check import ClaudeCliCheck, ClaudeCliCheckConfig
from app.modules.providers.connection_tester import ProviderConnectionTester
from app.modules.providers.flow_extension import FlowExtensionBridge
from app.modules.providers.flow_ws_server import FlowWsServer
from app.modules.providers.provider_catalog import (
    PROVIDER_SPECS_BY_ID,
    MediaFeature,
    MediaKind,
    ProviderId,
)
from app.modules.providers.repository import ProviderRepository
from app.modules.providers.secret_box import SecretBox
from app.modules.providers.service import ProviderSettingService, ProviderSettingTools

BYTES_PER_MB = 1024 * 1024
VIDEO_CHECK_TIMEOUT_SEC = 30
MEDIA_API_TIMEOUT_SEC = 300.0
LOCAL_AUDIO_PROVIDER_IDS = (ProviderId.OMNIVOICE, ProviderId.ACE_STEP, ProviderId.YUE)


@dataclass(frozen=True)
class Container:
    job_service: JobService
    youtube_job_service: YoutubeJobService
    film_analysis_job_service: FilmAnalysisJobService
    prompt_preset_service: PromptPresetService
    app_setting_service: AppSettingService
    ai_model_setting_service: AiModelSettingService
    provider_setting_service: ProviderSettingService
    generation_service: GenerationService
    generation_worker: GenerationWorker
    flow_extension: FlowExtensionBridge
    film_clone_service: FilmCloneService
    clone_action_service: CloneActionService
    clone_editing_service: CloneEditingService
    clone_job_watcher: CloneJobWatcher
    film_project_service: FilmProjectService
    film_character_service: FilmCharacterService
    film_style_service: FilmStyleService
    film_voice_service: FilmVoiceService
    film_episode_service: EpisodeService
    film_scene_service: SceneService
    film_stage_runner: EpisodeStageRunner
    film_access: FilmAccess
    film_thumbnail_service: FilmThumbnailService
    film_result_files: FilmResultFiles
    film_request_service: FilmRequestService
    film_step_commands: EpisodeStepCommands
    flow_ws_server: FlowWsServer
    captcha_service: CaptchaVerifier
    worker: BatchWorker
    command_runner: CommandRunner
    http_client: httpx.Client
    provider_http_client: httpx.Client


@dataclass(frozen=True)
class _GenerationParts:
    provider_setting_service: ProviderSettingService
    generation_service: GenerationService
    generation_worker: GenerationWorker
    flow_extension: FlowExtensionBridge
    flow_ws_server: FlowWsServer
    http_client: httpx.Client
    request_repository: GenerationRequestRepository
    targets_by_kind: dict[GenerationKind, GenerationTarget]


@dataclass(frozen=True)
class _CloneParts:
    repository: FilmCloneRepository
    files: CloneFiles
    image_queue: CloneImageQueue
    scene_image_check: CloneSceneImageCheck
    step_tools: CloneStepTools
    ai_activity: AiActivityTracker


@dataclass(frozen=True)
class _FilmParts:
    project_service: FilmProjectService
    character_service: FilmCharacterService
    style_service: FilmStyleService
    voice_service: FilmVoiceService
    episode_service: EpisodeService
    scene_service: SceneService
    stage_runner: EpisodeStageRunner
    access: FilmAccess
    thumbnail_service: FilmThumbnailService
    result_files: FilmResultFiles
    request_service: FilmRequestService
    step_commands: EpisodeStepCommands
    step_runner: EpisodeStepRunner


@dataclass(frozen=True)
class _Infrastructure:
    runner: CommandRunner
    storage: JobStorage
    repository: JobRepository


@dataclass(frozen=True)
class _SharedTools:
    infrastructure: _Infrastructure
    media: FfmpegMediaProcessor
    transcriber: WhisperCppTranscriber
    transcript_fetcher: YoutubeTranscriptFetcher
    downloader: YtDlpDownloader
    ai_caller: AiCaller
    moment_steps: MomentPickingSteps
    frame_capturer: MomentFrameCapturer


@dataclass(frozen=True)
class _AiParts:
    api_tools: AiApiTools
    step_models: AiStepModels


def build_container(settings: Settings) -> Container:
    session_factory = create_session_factory(settings.database_url)
    infrastructure = _Infrastructure(
        runner=CommandRunner(),
        storage=JobStorage(settings.storage_dir, settings.max_upload_mb * BYTES_PER_MB),
        repository=JobRepository(session_factory),
    )
    app_setting_repository = AppSettingRepository(session_factory)
    app_setting_service = AppSettingService(app_setting_repository)
    generation = _build_generation(
        _GenerationBuildInputs(
            settings=settings,
            session_factory=session_factory,
            runner=infrastructure.runner,
            app_setting_service=app_setting_service,
        )
    )
    ai_parts = _AiParts(
        api_tools=AiApiTools(
            http_client=generation.http_client,
            find_api_key=generation.provider_setting_service.find_api_key,
            image_encoding=AiImageEncoding(
                settings.ai_image_max_side_px, settings.ai_image_jpeg_quality
            ),
        ),
        step_models=AiStepModels(
            app_setting_service, generation.provider_setting_service.is_set_up
        ),
    )
    shared_tools = _build_shared_tools(
        settings, infrastructure, _build_ai_caller(settings, infrastructure.runner, ai_parts)
    )
    clone_parts = _build_clone_parts(
        _CloneBuildInputs(
            settings=settings,
            session_factory=session_factory,
            shared_tools=shared_tools,
            generation=generation,
            app_setting_service=app_setting_service,
        )
    )
    worker = BatchWorker(
        infrastructure.repository,
        {
            **_build_markdown_handlers(settings, shared_tools),
            **_build_film_analysis_handlers(
                settings, shared_tools, CloneFrameSaver(clone_parts.step_tools)
            ),
        },
        settings.batch_poll_interval_sec,
    )
    clone_job_watcher = CloneJobWatcher(clone_parts.repository)
    worker.add_finish_listener(clone_job_watcher)
    worker.add_idle_task(CloneStepRunner(clone_parts.step_tools))
    generation.targets_by_kind[GenerationKind.CLONE_REFERENCE_IMAGE] = CloneReferenceTarget(
        clone_parts.repository,
        clone_parts.files,
        CloneReferenceCheck(clone_parts.repository, worker.notify).check,
    )
    prompt_preset_service = PromptPresetService(PromptPresetRepository(session_factory))
    film_parts = _build_film_parts(
        _FilmBuildInputs(
            settings=settings,
            session_factory=session_factory,
            shared_tools=shared_tools,
            generation=generation,
            prompt_preset_service=prompt_preset_service,
            ai_parts=ai_parts,
            notify_batch_worker=worker.notify,
        )
    )
    worker.add_idle_task(film_parts.step_runner)
    intake = JobIntake(
        JobIntakeTools(
            repository=infrastructure.repository,
            preset_service=prompt_preset_service,
            settings_service=app_setting_service,
            step_models=ai_parts.step_models,
            notify_worker=worker.notify,
        )
    )
    http_client = create_captcha_http_client()
    video_checker = _build_youtube_video_checker(settings, infrastructure.runner)
    clone_access = CloneAccess(clone_parts.repository, generation.generation_service)
    return Container(
        job_service=JobService(infrastructure.repository, infrastructure.storage, intake),
        youtube_job_service=YoutubeJobService(video_checker, intake),
        film_analysis_job_service=FilmAnalysisJobService(
            infrastructure.repository, infrastructure.storage, intake
        ),
        prompt_preset_service=prompt_preset_service,
        app_setting_service=app_setting_service,
        ai_model_setting_service=AiModelSettingService(
            AiModelSettingTools(
                repository=app_setting_repository,
                setting_service=app_setting_service,
                provider_service=generation.provider_setting_service,
            )
        ),
        provider_setting_service=generation.provider_setting_service,
        generation_service=generation.generation_service,
        generation_worker=generation.generation_worker,
        flow_extension=generation.flow_extension,
        film_clone_service=FilmCloneService(
            FilmCloneServiceTools(
                repository=clone_parts.repository,
                job_repository=infrastructure.repository,
                job_storage=infrastructure.storage,
                files=clone_parts.files,
                intake=intake,
                video_checker=video_checker,
                generation_service=generation.generation_service,
                notify_worker=worker.notify,
                ai_activity=clone_parts.ai_activity,
            ),
            clone_access,
        ),
        clone_action_service=CloneActionService(
            CloneActionTools(
                repository=clone_parts.repository,
                job_repository=infrastructure.repository,
                files=clone_parts.files,
                app_setting_service=app_setting_service,
                image_queue=clone_parts.image_queue,
                scene_image_check=clone_parts.scene_image_check,
                notify_worker=worker.notify,
            ),
            clone_access,
        ),
        clone_editing_service=CloneEditingService(
            CloneEditingTools(
                repository=clone_parts.repository,
                files=clone_parts.files,
                image_queue=clone_parts.image_queue,
            ),
            clone_access,
        ),
        clone_job_watcher=clone_job_watcher,
        film_project_service=film_parts.project_service,
        film_character_service=film_parts.character_service,
        film_style_service=film_parts.style_service,
        film_voice_service=film_parts.voice_service,
        film_episode_service=film_parts.episode_service,
        film_scene_service=film_parts.scene_service,
        film_stage_runner=film_parts.stage_runner,
        film_access=film_parts.access,
        film_thumbnail_service=film_parts.thumbnail_service,
        film_result_files=film_parts.result_files,
        film_request_service=film_parts.request_service,
        film_step_commands=film_parts.step_commands,
        flow_ws_server=generation.flow_ws_server,
        captcha_service=create_captcha_service(settings, http_client),
        worker=worker,
        command_runner=infrastructure.runner,
        http_client=http_client,
        provider_http_client=generation.http_client,
    )


def close_container(container: Container) -> None:
    container.worker.stop()
    container.generation_worker.stop()
    container.command_runner.terminate_all()
    container.film_step_commands.terminate_all()
    container.worker.wait_until_stopped()
    container.generation_worker.wait_until_stopped()
    container.flow_ws_server.stop()
    container.http_client.close()
    container.provider_http_client.close()


def _build_ai_caller(settings: Settings, runner: CommandRunner, ai_parts: _AiParts) -> AiCaller:
    api_tools = ai_parts.api_tools
    return AiCaller(
        {
            ProviderId.CLAUDE_CLI: ClaudeCliClient(
                ClaudeCliConfig(settings.claude_bin, api_tools.image_encoding), runner
            ),
            ProviderId.GOOGLE: GeminiClient(api_tools),
            ProviderId.OPENAI: OpenAiClient(api_tools),
        },
        ai_parts.step_models,
    )


def _build_shared_tools(
    settings: Settings, infrastructure: _Infrastructure, ai_caller: AiCaller
) -> _SharedTools:
    runner = infrastructure.runner
    media = FfmpegMediaProcessor(
        FfmpegConfig(settings.ffmpeg_bin, settings.ffprobe_bin, settings.media_timeout_sec),
        runner,
    )
    downloader = YtDlpDownloader(
        YtDlpConfig(
            settings.ytdlp_bin, settings.youtube_timeout_sec, settings.youtube_video_height
        ),
        runner,
    )
    return _SharedTools(
        infrastructure=infrastructure,
        media=media,
        transcriber=WhisperCppTranscriber(
            WhisperConfig(
                settings.whisper_bin, settings.whisper_model_path, settings.whisper_timeout_sec
            ),
            runner,
        ),
        transcript_fetcher=YoutubeTranscriptFetcher(
            downloader, infrastructure.repository, infrastructure.storage
        ),
        downloader=downloader,
        ai_caller=ai_caller,
        moment_steps=MomentPickingSteps(
            KeyMomentPicker(
                ai_caller,
                infrastructure.repository,
                MomentPickerConfig(
                    limits=AiLimits(timeout_sec=settings.ai_moments_timeout_sec),
                    max_images_by_provider=to_max_images_by_provider(settings),
                ),
            ),
            FrameSampler(infrastructure.storage, media, settings.sample_frame_width),
        ),
        frame_capturer=MomentFrameCapturer(infrastructure.storage, media),
    )


def _build_markdown_handlers(
    settings: Settings, shared_tools: _SharedTools
) -> dict[JobType, JobHandler]:
    storage = shared_tools.infrastructure.storage
    return {
        JobType.VIDEO_TO_MARKDOWN: VideoToMarkdownHandler(
            storage,
            VideoToMarkdownTools(
                media=shared_tools.media,
                transcriber=shared_tools.transcriber,
                moment_steps=shared_tools.moment_steps,
            ),
            settings.max_moments,
        ),
        JobType.YOUTUBE_TO_MARKDOWN: YoutubeToMarkdownHandler(
            storage,
            YoutubeToMarkdownTools(
                transcript_fetcher=shared_tools.transcript_fetcher,
                downloader=shared_tools.downloader,
                moment_steps=shared_tools.moment_steps,
                frame_capturer=shared_tools.frame_capturer,
            ),
            settings.max_moments,
        ),
    }


def _build_film_analysis_handlers(
    settings: Settings, shared_tools: _SharedTools, clone_passes: NotesPasses
) -> dict[JobType, JobHandler]:
    infrastructure = shared_tools.infrastructure
    frame_steps = FilmFrameSteps(
        infrastructure.repository,
        FilmFrameTools(
            moment_steps=shared_tools.moment_steps,
            scene_detector=FfmpegSceneDetector(
                SceneDetectorConfig(
                    settings.ffmpeg_bin,
                    settings.film_scene_threshold,
                    settings.film_scene_timeout_sec,
                ),
                infrastructure.runner,
            ),
            frame_capturer=shared_tools.frame_capturer,
        ),
    )
    prompt_passes = FilmPromptPasses(
        PromptPassTools(
            storage=infrastructure.storage,
            repository=infrastructure.repository,
            ai_caller=shared_tools.ai_caller,
            limits=AiLimits(timeout_sec=settings.film_prompt_timeout_sec),
            max_images_by_provider=to_max_images_by_provider(settings),
        )
    )
    return {
        JobType.FILM_ANALYSIS: FilmAnalysisHandler(
            infrastructure.storage,
            infrastructure.repository,
            FilmAnalysisTools(
                media=shared_tools.media,
                transcriber=shared_tools.transcriber,
                frame_steps=frame_steps,
                prompt_passes=prompt_passes,
            ),
        ),
        JobType.YOUTUBE_FILM_ANALYSIS: YoutubeFilmAnalysisHandler(
            infrastructure.storage,
            infrastructure.repository,
            YoutubeFilmAnalysisTools(
                transcript_fetcher=shared_tools.transcript_fetcher,
                downloader=shared_tools.downloader,
                frame_steps=frame_steps,
                prompt_passes=prompt_passes,
            ),
        ),
        JobType.FILM_ANALYSIS_RERUN: FilmAnalysisRerunHandler(
            infrastructure.repository, prompt_passes
        ),
        JobType.FILM_CLONE: FilmAnalysisHandler(
            infrastructure.storage,
            infrastructure.repository,
            FilmAnalysisTools(
                media=shared_tools.media,
                transcriber=shared_tools.transcriber,
                frame_steps=frame_steps,
                prompt_passes=clone_passes,
            ),
        ),
        JobType.YOUTUBE_FILM_CLONE: YoutubeFilmAnalysisHandler(
            infrastructure.storage,
            infrastructure.repository,
            YoutubeFilmAnalysisTools(
                transcript_fetcher=shared_tools.transcript_fetcher,
                downloader=shared_tools.downloader,
                frame_steps=frame_steps,
                prompt_passes=clone_passes,
            ),
        ),
    }


def _build_youtube_video_checker(settings: Settings, runner: CommandRunner) -> YoutubeVideoChecker:
    downloader = YtDlpDownloader(
        YtDlpConfig(settings.ytdlp_bin, VIDEO_CHECK_TIMEOUT_SEC, settings.youtube_video_height),
        runner,
    )
    return YoutubeVideoChecker(downloader, settings.youtube_max_duration_min)


def to_max_images_by_provider(settings: Settings) -> dict[ProviderId, int]:
    return {
        ProviderId.CLAUDE_CLI: settings.claude_max_images_per_call,
        ProviderId.GOOGLE: settings.gemini_max_images_per_call,
        ProviderId.OPENAI: settings.openai_max_images_per_call,
    }


@dataclass(frozen=True)
class _GenerationBuildInputs:
    settings: Settings
    session_factory: sessionmaker[Session]
    runner: CommandRunner
    app_setting_service: AppSettingService


def _build_generation(inputs: _GenerationBuildInputs) -> _GenerationParts:
    settings = inputs.settings
    session_factory = inputs.session_factory
    http_client = httpx.Client()
    flow_extension = FlowExtensionBridge()
    request_repository = GenerationRequestRepository(session_factory)
    provider_setting_service = ProviderSettingService(
        ProviderRepository(session_factory),
        ProviderSettingTools(
            secret_box=SecretBox(settings.settings_secret_key),
            connection_tester=ProviderConnectionTester(
                http_client, flow_extension, settings.provider_test_timeout_sec
            ),
            extension=flow_extension,
            queue_counter=request_repository,
            claude_cli_check=ClaudeCliCheck(
                ClaudeCliCheckConfig(settings.claude_bin, settings.provider_test_timeout_sec),
                inputs.runner,
            ),
            chosen_provider_settings=inputs.app_setting_service,
        ),
    )
    targets_by_kind: dict[GenerationKind, GenerationTarget] = {}
    flow_adapter = GoogleFlowAdapter(
        GoogleFlowTools(
            bridge=flow_extension,
            http_client=http_client,
            owners=RepositoryFlowProjectOwners(
                FlowProjectOwnerRepositories(
                    requests=request_repository,
                    films=FilmRepository(session_factory),
                    clones=FilmCloneRepository(session_factory),
                )
            ),
        )
    )
    worker = GenerationWorker(
        GenerationWorkerTools(
            repository=request_repository,
            provider_service=provider_setting_service,
            adapters_by_provider={
                **_build_media_adapters(settings, http_client),
                ProviderId.GOOGLE_FLOW: flow_adapter,
            },
            targets_by_kind=targets_by_kind,
            flow_extension=flow_extension,
            clip_editor=FfmpegClipEditor(
                ClipEditorConfig(settings.ffmpeg_bin, settings.media_timeout_sec), inputs.runner
            ),
        ),
        GenerationWorkerConfig(
            poll_interval_sec=settings.film_worker_poll_interval_sec,
            max_attempts=settings.film_request_max_attempts,
        ),
    )
    return _GenerationParts(
        provider_setting_service=provider_setting_service,
        generation_service=GenerationService(
            request_repository, provider_setting_service, targets_by_kind, worker.notify
        ),
        generation_worker=worker,
        flow_extension=flow_extension,
        flow_ws_server=FlowWsServer(flow_extension, settings.flow_ws_port),
        http_client=http_client,
        request_repository=request_repository,
        targets_by_kind=targets_by_kind,
    )


@dataclass(frozen=True)
class _CloneBuildInputs:
    settings: Settings
    session_factory: sessionmaker[Session]
    shared_tools: _SharedTools
    generation: _GenerationParts
    app_setting_service: AppSettingService


def _build_clone_parts(inputs: _CloneBuildInputs) -> _CloneParts:
    settings = inputs.settings
    shared_tools = inputs.shared_tools
    generation = inputs.generation
    infrastructure = shared_tools.infrastructure
    repository = FilmCloneRepository(inputs.session_factory)
    files = CloneFiles(settings.storage_dir)
    image_queue = CloneImageQueue(generation.generation_service, infrastructure.storage)
    scene_image_check = CloneSceneImageCheck(repository)
    ai_activity = AiActivityTracker()
    generation.targets_by_kind[GenerationKind.CLONE_SCENE_IMAGE] = CloneSceneImageTarget(
        repository, files, scene_image_check.check
    )
    return _CloneParts(
        repository=repository,
        ai_activity=ai_activity,
        files=files,
        image_queue=image_queue,
        scene_image_check=scene_image_check,
        step_tools=CloneStepTools(
            repository=repository,
            job_repository=infrastructure.repository,
            job_storage=infrastructure.storage,
            ai_caller=WatchedCloneAiCaller(
                shared_tools.ai_caller,
                AiLimits(
                    timeout_sec=settings.clone_ai_max_run_sec,
                    silence_limit_sec=settings.clone_ai_silence_sec,
                ),
                ai_activity,
            ),
            image_queue=image_queue,
            app_setting_service=inputs.app_setting_service,
            max_images_by_provider=to_max_images_by_provider(settings),
            script_shots_per_call=settings.clone_script_shots_per_call,
        ),
    )


def _build_media_adapters(
    settings: Settings, http_client: httpx.Client
) -> dict[ProviderId, MediaProviderAdapter]:
    return {
        ProviderId.GOOGLE: GoogleAiAdapter(http_client, MEDIA_API_TIMEOUT_SEC),
        ProviderId.FAL: FalAdapter(http_client, MEDIA_API_TIMEOUT_SEC),
        ProviderId.REPLICATE: ReplicateAdapter(http_client, MEDIA_API_TIMEOUT_SEC),
        ProviderId.OPENAI: OpenAiImageAdapter(http_client, MEDIA_API_TIMEOUT_SEC),
        ProviderId.ELEVENLABS: ElevenLabsAdapter(http_client, MEDIA_API_TIMEOUT_SEC),
        **{
            provider_id: LocalAudioAdapter(
                http_client,
                settings.local_server_timeout_sec,
                PROVIDER_SPECS_BY_ID[provider_id].name,
            )
            for provider_id in LOCAL_AUDIO_PROVIDER_IDS
        },
        ProviderId.SD_WEBUI: SdWebUiAdapter(
            http_client,
            SdWebUiConfig(
                timeout_sec=settings.local_server_timeout_sec,
                denoising_strength=settings.sd_denoising_strength,
                composite_denoising_strength=settings.sd_composite_denoising_strength,
            ),
        ),
    }


@dataclass(frozen=True)
class _FilmBuildInputs:
    settings: Settings
    session_factory: sessionmaker[Session]
    shared_tools: _SharedTools
    generation: _GenerationParts
    prompt_preset_service: PromptPresetService
    ai_parts: _AiParts
    notify_batch_worker: Callable[[], None]


@dataclass(frozen=True)
class _FilmCore:
    repository: FilmRepository
    files: FilmFiles
    access: FilmAccess
    media_queue: FilmMediaQueue
    imports: FilmImports
    stage_runner: EpisodeStageRunner
    step_commands: EpisodeStepCommands


def _build_film_parts(inputs: _FilmBuildInputs) -> _FilmParts:
    core = _build_film_core(inputs)
    settings = inputs.settings
    infrastructure = inputs.shared_tools.infrastructure
    analysis_source = AnalysisSource(
        AnalysisSourceTools(
            files=core.files,
            job_repository=infrastructure.repository,
            job_storage=infrastructure.storage,
        )
    )
    return _FilmParts(
        project_service=FilmProjectService(
            FilmProjectTools(
                repository=core.repository, files=core.files, media_queue=core.media_queue
            )
        ),
        character_service=FilmCharacterService(core.repository, core.files),
        style_service=FilmStyleService(core.repository),
        voice_service=FilmVoiceService(
            FilmVoiceTools(
                repository=core.repository,
                files=core.files,
                media=inputs.shared_tools.media,
                transcriber=inputs.shared_tools.transcriber,
            )
        ),
        episode_service=_build_episode_service(inputs, core, analysis_source),
        scene_service=SceneService(
            SceneServiceTools(
                repository=core.repository,
                access=core.access,
                files=core.files,
                media_queue=core.media_queue,
            )
        ),
        stage_runner=core.stage_runner,
        access=core.access,
        thumbnail_service=FilmThumbnailService(
            ThumbnailServiceTools(
                access=core.access,
                repository=core.repository,
                files=core.files,
                media_queue=core.media_queue,
                cropper=FfmpegThumbnailCropper(
                    CropperConfig(settings.ffmpeg_bin, settings.media_timeout_sec),
                    infrastructure.runner,
                ),
            )
        ),
        result_files=FilmResultFiles(core.access, core.files),
        request_service=FilmRequestService(
            FilmRequestTools(
                repository=core.repository,
                request_repository=inputs.generation.request_repository,
                generation_service=inputs.generation.generation_service,
            )
        ),
        step_commands=core.step_commands,
        step_runner=_build_episode_step_runner(inputs, core, analysis_source),
    )


def _build_film_core(inputs: _FilmBuildInputs) -> _FilmCore:
    generation = inputs.generation
    repository = FilmRepository(inputs.session_factory)
    files = FilmFiles(inputs.settings.storage_dir, inputs.settings.film_upload_max_mb)
    media_queue = FilmMediaQueue(
        repository,
        files,
        generation.generation_service,
        lambda: generation.provider_setting_service.pick_provider(
            MediaKind.SPEECH, MediaFeature.FILM_STUDIO
        ),
    )
    step_commands = EpisodeStepCommands()
    stage_runner = EpisodeStageRunner(
        StageRunnerTools(
            repository=repository,
            files=files,
            media_queue=media_queue,
            generation_service=generation.generation_service,
            notify_step_worker=inputs.notify_batch_worker,
            cancel_worker_step=step_commands.cancel,
        )
    )
    generation.targets_by_kind.update(
        build_film_targets(
            FilmTargetTools(
                repository=repository,
                files=files,
                request_repository=generation.request_repository,
                duration_probe=inputs.shared_tools.media,
                on_final=stage_runner.on_request_final,
            )
        )
    )
    return _FilmCore(
        repository=repository,
        files=files,
        access=FilmAccess(repository),
        media_queue=media_queue,
        imports=FilmImports(files),
        stage_runner=stage_runner,
        step_commands=step_commands,
    )


def _build_episode_service(
    inputs: _FilmBuildInputs, core: _FilmCore, analysis_source: AnalysisSource
) -> EpisodeService:
    infrastructure = inputs.shared_tools.infrastructure
    clone_source = CloneSource(
        CloneSourceTools(
            repository=core.repository,
            files=core.files,
            imports=core.imports,
            clone_repository=FilmCloneRepository(inputs.session_factory),
            clone_files=CloneFiles(inputs.settings.storage_dir),
            job_storage=infrastructure.storage,
        )
    )
    return EpisodeService(
        EpisodeServiceTools(
            repository=core.repository,
            access=core.access,
            files=core.files,
            imports=core.imports,
            preset_service=inputs.prompt_preset_service,
            step_models=inputs.ai_parts.step_models,
            analysis_source=analysis_source,
            clone_source=clone_source,
        )
    )


def _build_episode_step_runner(
    inputs: _FilmBuildInputs, core: _FilmCore, analysis_source: AnalysisSource
) -> EpisodeStepRunner:
    settings = inputs.settings
    runner = core.step_commands
    script_writer = EpisodeScriptWriter(
        ScriptWriterTools(
            repository=core.repository,
            imports=core.imports,
            analysis_source=analysis_source,
            ai_caller=_build_ai_caller(settings, runner, inputs.ai_parts),
            limits=AiLimits(timeout_sec=settings.film_script_timeout_sec),
        )
    )
    assembler = FfmpegEpisodeAssembler(
        AssemblerConfig(
            ffmpeg_bin=settings.ffmpeg_bin,
            ffprobe_bin=settings.ffprobe_bin,
            timeout_sec=settings.film_assembly_timeout_sec,
            music_volume=settings.film_music_volume,
            work_root=Path(tempfile.gettempdir()),
        ),
        AssemblerTools(repository=core.repository, files=core.files, runner=runner),
    )
    return EpisodeStepRunner(
        EpisodeStepTools(
            repository=core.repository,
            stage_runner=core.stage_runner,
            script_writer=script_writer,
            assembler=assembler,
            commands=core.step_commands,
        )
    )
