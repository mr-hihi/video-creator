import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any
from uuid import uuid4

from PIL import Image

from app.common.sequences import split_into_batches, spread_evenly
from app.db import utc_now
from app.modules.ai_models.ai_calls import AiAsk, AiModelChoice, AttachedImage
from app.modules.ai_models.model_choices import to_ai_name
from app.modules.app_settings.service import AppSettingService
from app.modules.film_clones.clone_access import is_waiting_at
from app.modules.film_clones.clone_ai_caller import WatchedCloneAiCaller
from app.modules.film_clones.clone_catalog import (
    CAMERA_ANGLE_LABELS,
    EMPTY_LABEL,
    LANGUAGE_NAMES_BY_CODE,
    SHOT_SIZE_LABELS,
    TARGET_COUNTRIES_BY_CODE,
)
from app.modules.film_clones.clone_generation import CloneImageQueue
from app.modules.film_clones.clone_replies import (
    ASSETS_REPLY_SCHEMA,
    LOCALIZATION_REPLY_SCHEMA,
    SCENES_LIST_KEY,
    SCRIPT_REPLY_SCHEMA,
    SHOTS_LIST_KEY,
    SHOTS_REPLY_SCHEMA,
    AnalyzedShot,
    ExpectedScript,
    ExtractedAsset,
    FrameInfo,
    find_placed_frames,
    find_unmatched_frames,
    join_batch_replies,
    normalize_assets,
    normalize_localization,
    normalize_script,
    normalize_shots,
)
from app.modules.film_clones.errors import CloneStepFailedError
from app.modules.film_clones.localization_rules import (
    clone_to_localization_choices,
    find_assets_missing_reference,
    find_candidates,
    find_ticked_flags,
    find_transcript_language,
    resolve_script_language,
    to_localization_values,
)
from app.modules.film_clones.models import (
    CloneAspect,
    CloneAsset,
    CloneImageStatus,
    CloneScene,
    CloneShot,
    CloneStatus,
    CloneStep,
    FilmClone,
    FrameKind,
)
from app.modules.film_clones.repository import LOCALIZED_FIELDS_CLEARED, FilmCloneRepository
from app.modules.jobs.film_analysis.frames import SCENE_CHANGE_TITLE
from app.modules.jobs.film_analysis.notes_passes import WrittenNotes
from app.modules.jobs.job_prompts import PROMPTS_OPTION_KEY, get_job_prompt
from app.modules.jobs.models import Job, JobOutputKind, JobStatus, JobStep
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.storage import JobStorage, to_safe_stem
from app.modules.jobs.video_to_markdown.moments import KeyMoment
from app.modules.jobs.video_to_markdown.transcript import format_timestamp
from app.modules.prompt_presets.prompt_texts import (
    CloneLocalizationRequestText,
    CloneScriptRequestText,
    PromptKey,
    build_clone_localization_message,
    build_clone_script_message,
    build_clone_shots_message,
    build_video_notes_message,
)
from app.modules.providers.provider_catalog import ProviderId

FINAL_IMAGE_STATUSES = frozenset({CloneImageStatus.DONE, CloneImageStatus.FAILED})
WRITING_SCRIPT_VALUES = {"status": CloneStatus.RUNNING, "step": CloneStep.WRITING_SCRIPT}
WAITING_FOR_CHOICES_VALUES = {
    "status": CloneStatus.WAITING,
    "step": CloneStep.CHOOSING_LOCALIZATION,
}
REPLY_SCHEMAS_BY_PROMPT_KEY = {
    PromptKey.CLONE_ASSETS: ASSETS_REPLY_SCHEMA,
    PromptKey.CLONE_SHOTS: SHOTS_REPLY_SCHEMA,
}
BACKGROUND_STEPS = (
    CloneStep.EXTRACTING_ASSETS,
    CloneStep.ANALYZING_SHOTS,
    CloneStep.PROPOSING,
    CloneStep.WRITING_SCRIPT,
)
MAX_LOGGED_FRAMES = 5
NO_SHOTS_MESSAGE = "{model} returned no shots"
NO_CAPTURED_FRAME_MESSAGE = "{model} named no captured frame: {frames}"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CloneStepTools:
    repository: FilmCloneRepository
    job_repository: JobRepository
    job_storage: JobStorage
    ai_caller: WatchedCloneAiCaller
    image_queue: CloneImageQueue
    app_setting_service: AppSettingService
    max_images_by_provider: Mapping[ProviderId, int]
    script_shots_per_call: int


@dataclass(frozen=True)
class FramesQuestion:
    prompt_key: PromptKey
    message: str
    shots: Sequence[CloneShot]


class CloneFrameSaver:
    def __init__(self, tools: CloneStepTools):
        self._tools = tools

    def run(self, job: Job, notes: WrittenNotes, report_step: Callable[[JobStep], None]) -> None:
        clone = self._tools.repository.find_by_job_id(job.id)
        if clone is None:
            raise CloneStepFailedError(f"No film clone uses job {job.id}")
        frames = [
            to_frame_info(captured.moment, captured.image_relative_path)
            for captured in notes.captured_moments
        ]
        self._tools.repository.replace_assets_and_shots(
            clone.id, [], to_frame_rows(clone.id, frames)
        )
        self._tools.repository.update_clone(clone.id, {"aspect": self._find_aspect(job.id, frames)})

    def _find_aspect(self, job_id: str, frames: Sequence[FrameInfo]) -> CloneAspect:
        if not frames:
            return CloneAspect.LANDSCAPE
        with Image.open(self._tools.job_storage.output_dir(job_id) / frames[0].frame) as image:
            width, height = image.size
        return CloneAspect.LANDSCAPE if width >= height else CloneAspect.PORTRAIT


class CloneJobWatcher:
    def __init__(self, repository: FilmCloneRepository):
        self._repository = repository

    def on_job_finished(self, job_id: str) -> None:
        clone = self._repository.find_by_job_id(job_id)
        if clone is not None:
            self._apply_job_result(clone)

    def apply_finished_jobs(self) -> None:
        for clone in self._repository.find_analyzing():
            self._apply_job_result(clone)

    def _apply_job_result(self, clone: FilmClone) -> None:
        job = self._repository.find_jobs([clone.job_id]).get(clone.job_id)
        if job is None or job.status not in (JobStatus.DONE, JobStatus.FAILED):
            return
        if job.status is JobStatus.DONE:
            values = {"status": CloneStatus.RUNNING, "step": CloneStep.EXTRACTING_ASSETS}
        else:
            values = {"status": CloneStatus.FAILED, "error_message": job.error_message}
        self._repository.update_clone_if_step(clone.id, CloneStep.ANALYZING, values)


class CloneStepRunner:
    def __init__(self, tools: CloneStepTools):
        self._tools = tools
        self._run_by_step: dict[CloneStep, Callable[[FilmClone], None]] = {
            CloneStep.EXTRACTING_ASSETS: self._extract_assets,
            CloneStep.ANALYZING_SHOTS: self._analyze_shots,
            CloneStep.PROPOSING: self._propose,
            CloneStep.WRITING_SCRIPT: self._write_script,
        }

    def run_next(self, is_stopping: Callable[[], bool]) -> bool:
        clone = self._tools.repository.find_oldest_running(BACKGROUND_STEPS)
        if clone is None:
            return False
        logger.info("Film clone %s: %s started", clone.id, clone.step)
        started_at = time.monotonic()
        try:
            self._run_by_step[clone.step](clone)
            logger.info(
                "Film clone %s: %s finished in %ds",
                clone.id,
                clone.step,
                time.monotonic() - started_at,
            )
        except Exception as error:
            if is_stopping():
                logger.warning(
                    "Film clone %s: %s interrupted by shutdown; runs again on next start",
                    clone.id,
                    clone.step,
                )
                return True
            logger.exception("Film clone %s: %s failed", clone.id, clone.step)
            self._tools.repository.update_clone(
                clone.id,
                {"status": CloneStatus.FAILED, "error_message": str(error) or type(error).__name__},
            )
        return True

    def _extract_assets(self, clone: FilmClone) -> None:
        job = self._find_job(clone)
        shots = self._tools.repository.find_shots(clone.id)
        choice = self._start_ai_call(clone)
        question = FramesQuestion(
            PromptKey.CLONE_ASSETS,
            build_video_notes_message(self._find_video_notes(job.id)),
            spread_evenly(shots, self._tools.max_images_by_provider[choice.provider]),
        )
        reply = self._tools.ai_caller.ask(clone.id, choice, self._to_frames_ask(job, question))
        assets = to_asset_rows(clone.id, normalize_assets(reply, [shot.frame for shot in shots]))
        self._tools.repository.save_assets(clone.id, assets, {"step": CloneStep.ANALYZING_SHOTS})

    def _analyze_shots(self, clone: FilmClone) -> None:
        job = self._find_job(clone)
        shots = self._tools.repository.find_shots(clone.id)
        assets = self._tools.repository.find_assets(clone.id)
        frames = [
            FrameInfo(frame=shot.frame, at_ms=shot.at_ms, kind=shot.frame_kind) for shot in shots
        ]
        video_notes = self._find_video_notes(job.id)
        message = build_clone_shots_message(
            video_notes, [f"{asset.name} ({asset.kind.value})" for asset in assets]
        )
        choice = self._start_ai_call(clone)
        shot_asks = self._to_frames_asks(
            job,
            FramesQuestion(PromptKey.CLONE_SHOTS, message, shots),
            self._tools.max_images_by_provider[choice.provider],
        )
        reply = join_batch_replies(self._ask_each(clone.id, choice, shot_asks), SHOTS_LIST_KEY)
        analyzed_shots = normalize_shots(reply, frames, [asset.name for asset in assets])
        unmatched_frames = find_unmatched_frames(reply, frames)
        if not find_placed_frames(reply, frames):
            raise CloneStepFailedError(
                describe_unplaced_shots(unmatched_frames, to_ai_name(choice.provider))
            )
        if unmatched_frames:
            logger.warning(
                "Film clone %s: %d shot entries name no captured frame: %s",
                clone.id,
                len(unmatched_frames),
                unmatched_frames[:MAX_LOGGED_FRAMES],
            )
        asset_ids_by_name = {asset.name: asset.id for asset in assets}
        self._tools.repository.save_shot_analysis(
            clone.id,
            {
                shot.id: to_shot_values(analyzed_shot, asset_ids_by_name)
                for shot, analyzed_shot in zip(shots, analyzed_shots, strict=True)
            },
            self._build_values_after_shots(clone, video_notes),
        )

    def _build_values_after_shots(self, clone: FilmClone, video_notes: str) -> dict[str, Any]:
        if not clone.should_run_automatically:
            return WAITING_FOR_CHOICES_VALUES
        script_language = resolve_script_language(
            self._tools.app_setting_service.get_script_language(),
            clone.target_country,
            find_transcript_language(video_notes),
        )
        return to_localization_values(clone_to_localization_choices(clone), script_language)

    def _ask_each(
        self, clone_id: str, choice: AiModelChoice, asks: Sequence[AiAsk]
    ) -> list[dict[str, Any]]:
        return [self._tools.ai_caller.ask(clone_id, choice, ask) for ask in asks]

    def _start_ai_call(self, clone: FilmClone) -> AiModelChoice:
        choice = self._tools.ai_caller.find_model()
        self._tools.repository.save_ai_used(clone.id, clone.step, choice)
        return choice

    def _to_frames_ask(self, job: Job, question: FramesQuestion) -> AiAsk:
        output_dir = self._tools.job_storage.output_dir(job.id)
        return AiAsk(
            instructions=get_job_prompt(job.options, question.prompt_key),
            message=question.message,
            reply_schema=REPLY_SCHEMAS_BY_PROMPT_KEY[question.prompt_key],
            images=[
                AttachedImage(label=shot.frame, path=output_dir / shot.frame)
                for shot in question.shots
            ],
        )

    def _to_frames_asks(self, job: Job, question: FramesQuestion, batch_size: int) -> list[AiAsk]:
        return [
            self._to_frames_ask(job, replace(question, shots=batch))
            for batch in split_into_batches(question.shots, batch_size)
        ]

    def _find_job(self, clone: FilmClone) -> Job:
        job = self._tools.job_repository.find_by_id(clone.job_id)
        if job is None:
            raise CloneStepFailedError(f"Job {clone.job_id} of film clone {clone.id} not found")
        return job

    def _find_video_notes(self, job_id: str) -> str:
        return self._tools.job_repository.find_outputs(job_id).get(JobOutputKind.VIDEO_NOTES, "")

    def _propose(self, clone: FilmClone) -> None:
        flags = find_ticked_flags(clone)
        candidates = find_candidates(self._tools.repository.find_assets(clone.id), flags)
        if candidates:
            self._localize_candidates(clone, candidates, [flag.allowed_change for flag in flags])
        changed_assets = [
            asset for asset in self._tools.repository.find_assets(clone.id) if asset.changed
        ]
        if clone.should_run_automatically and not changed_assets:
            self._tools.repository.update_clone(clone.id, WRITING_SCRIPT_VALUES)
            return
        self._tools.repository.update_clone(
            clone.id, {"status": CloneStatus.WAITING, "step": CloneStep.REVIEWING}
        )
        for asset in changed_assets:
            self._tools.image_queue.queue_reference(clone, asset)

    def _localize_candidates(
        self, clone: FilmClone, candidates: Sequence[CloneAsset], allowed_changes: Sequence[str]
    ) -> None:
        reply = self._tools.ai_caller.ask(
            clone.id,
            self._start_ai_call(clone),
            AiAsk(
                instructions=self._clone_prompt(clone, PromptKey.CLONE_LOCALIZATION),
                message=build_clone_localization_message(
                    CloneLocalizationRequestText(
                        country_name=to_country_name(clone.target_country) or "",
                        target_setting=clone.target_setting,
                        allowed_changes=allowed_changes,
                        candidate_lines=[to_candidate_line(asset) for asset in candidates],
                    )
                ),
                reply_schema=LOCALIZATION_REPLY_SCHEMA,
                images=[
                    AttachedImage(
                        label=asset.reference_frame,
                        path=self._tools.job_storage.output_dir(clone.job_id)
                        / asset.reference_frame,
                    )
                    for asset in candidates
                    if asset.reference_frame
                ],
            ),
        )
        proposals_by_name = normalize_localization(reply, [asset.name for asset in candidates])
        self._tools.repository.update_assets(
            {
                asset.id: {
                    **LOCALIZED_FIELDS_CLEARED,
                    "changed": proposals_by_name[asset.name].changed,
                    "localized_name": proposals_by_name[asset.name].localized_name,
                    "localized_description": proposals_by_name[asset.name].localized_description,
                    "localization_note": proposals_by_name[asset.name].note,
                }
                for asset in candidates
            }
        )

    def _write_script(self, clone: FilmClone) -> None:
        shots = self._tools.repository.find_shots(clone.id)
        choice = self._start_ai_call(clone)
        script = normalize_script(
            self._ask_for_script(clone, choice, shots),
            ExpectedScript(
                shot_ids=[shot.id for shot in shots],
                fallback_title=self._find_fallback_title(clone),
                ai_name=to_ai_name(choice.provider),
            ),
        )
        scenes = [
            CloneScene(
                id=str(uuid4()),
                clone_id=clone.id,
                shot_id=shot.id,
                position=shot.position,
                description=script.scenes_by_shot_id[shot.id].description,
                dialogue=script.scenes_by_shot_id[shot.id].dialogue,
                image_prompt=script.scenes_by_shot_id[shot.id].image_prompt,
                asset_ids=list(shot.asset_ids),
                image_status=CloneImageStatus.NONE,
            )
            for shot in shots
        ]
        self._tools.repository.save_scenes(
            clone.id,
            scenes,
            {
                "script_title": script.title,
                "logline": script.logline,
                "step": CloneStep.GENERATING_SCENE_IMAGES,
            },
        )
        for scene, shot in zip(scenes, shots, strict=True):
            self._tools.image_queue.queue_scene_image(clone, scene, shot)

    def _ask_for_script(
        self, clone: FilmClone, choice: AiModelChoice, shots: Sequence[CloneShot]
    ) -> dict:
        assets = self._tools.repository.find_assets(clone.id)
        names_by_asset_id = {asset.id: current_name(asset) for asset in assets}
        video_notes = self._find_video_notes(clone.job_id)
        script_asks = [
            AiAsk(
                instructions=self._clone_prompt(clone, PromptKey.CLONE_SCRIPT),
                message=build_clone_script_message(
                    CloneScriptRequestText(
                        language_name=to_language_name(clone.script_language),
                        country_name=to_country_name(clone.target_country),
                        target_setting=clone.target_setting,
                        asset_lines=[to_script_asset_line(asset) for asset in assets],
                        shot_lines=[to_shot_line(shot, names_by_asset_id) for shot in batch],
                        video_notes=video_notes,
                    )
                ),
                reply_schema=SCRIPT_REPLY_SCHEMA,
            )
            for batch in split_into_batches(shots, self._tools.script_shots_per_call)
        ]
        return join_batch_replies(self._ask_each(clone.id, choice, script_asks), SCENES_LIST_KEY)

    def _find_fallback_title(self, clone: FilmClone) -> str:
        job = self._tools.job_repository.find_by_id(clone.job_id)
        return to_safe_stem(job.source_filename) if job else clone.id

    def _clone_prompt(self, clone: FilmClone, prompt_key: PromptKey) -> str:
        return get_job_prompt({PROMPTS_OPTION_KEY: clone.prompts}, prompt_key)


class CloneReferenceCheck:
    def __init__(self, repository: FilmCloneRepository, notify_worker: Callable[[], None]):
        self._repository = repository
        self._notify_worker = notify_worker

    def check(self, clone_id: str) -> None:
        clone = self._repository.find_by_id(clone_id)
        if clone is None or not clone.should_run_automatically:
            return
        if not is_waiting_at(clone, CloneStep.REVIEWING):
            return
        if find_assets_missing_reference(self._repository.find_assets(clone_id)):
            return
        self._repository.update_clone(clone_id, WRITING_SCRIPT_VALUES)
        self._notify_worker()


class CloneSceneImageCheck:
    def __init__(self, repository: FilmCloneRepository):
        self._repository = repository

    def check(self, clone_id: str) -> None:
        clone = self._repository.find_by_id(clone_id)
        if clone is None or clone.step is not CloneStep.GENERATING_SCENE_IMAGES:
            return
        scenes = self._repository.find_scenes(clone_id)
        if any(scene.image_status not in FINAL_IMAGE_STATUSES for scene in scenes):
            return
        failed_count = sum(scene.image_status is not CloneImageStatus.DONE for scene in scenes)
        if failed_count:
            values = {
                "status": CloneStatus.FAILED,
                "error_message": f"{failed_count} scene image(s) failed — fix them and resume",
            }
        else:
            values = {
                "status": CloneStatus.DONE,
                "error_message": None,
                "finished_at": clone.finished_at or utc_now(),
            }
        self._repository.update_clone(clone_id, values)


def to_frame_info(moment: KeyMoment, image_relative_path: str) -> FrameInfo:
    kind = FrameKind.SCENE if moment.title == SCENE_CHANGE_TITLE else FrameKind.DIALOGUE
    return FrameInfo(frame=image_relative_path, at_ms=moment.at_ms, kind=kind)


def to_asset_rows(clone_id: str, extracted_assets: Sequence[ExtractedAsset]) -> list[CloneAsset]:
    return [
        CloneAsset(
            id=str(uuid4()),
            clone_id=clone_id,
            position=position,
            kind=asset.kind,
            name=asset.name,
            description=asset.description,
            culture=asset.culture,
            period=asset.period,
            frames=asset.frames,
            reference_frame=asset.frames[0] if asset.frames else None,
            **LOCALIZED_FIELDS_CLEARED,
        )
        for position, asset in enumerate(extracted_assets)
    ]


def describe_unplaced_shots(unmatched_frames: Sequence[str], ai_name: str) -> str:
    if not unmatched_frames:
        return NO_SHOTS_MESSAGE.format(model=ai_name)
    return NO_CAPTURED_FRAME_MESSAGE.format(
        model=ai_name, frames=list(unmatched_frames[:MAX_LOGGED_FRAMES])
    )


def to_frame_rows(clone_id: str, frames: Sequence[FrameInfo]) -> list[CloneShot]:
    return [
        CloneShot(
            id=str(uuid4()),
            clone_id=clone_id,
            position=position,
            at_ms=frame.at_ms,
            frame=frame.frame,
            frame_kind=frame.kind,
            shot_size=None,
            camera_angle=None,
            emotion=None,
            action=None,
            asset_ids=[],
        )
        for position, frame in enumerate(frames)
    ]


def to_shot_values(shot: AnalyzedShot, asset_ids_by_name: dict[str, str]) -> dict[str, Any]:
    return {
        "shot_size": shot.shot_size,
        "camera_angle": shot.camera_angle,
        "emotion": shot.emotion,
        "action": shot.action,
        "asset_ids": [asset_ids_by_name[name] for name in shot.asset_names],
    }


def to_language_name(language: str | None) -> str:
    return LANGUAGE_NAMES_BY_CODE.get(language or "", language or "")


def to_country_name(country_code: str | None) -> str | None:
    return TARGET_COUNTRIES_BY_CODE[country_code].name if country_code else None


def current_name(asset: CloneAsset) -> str:
    return asset.localized_name if asset.changed and asset.localized_name else asset.name


def to_candidate_line(asset: CloneAsset) -> str:
    return (
        f"{asset.name} ({asset.kind.value}) — {asset.description}. "
        f"Culture: {asset.culture}. Period: {asset.period}."
    )


def to_script_asset_line(asset: CloneAsset) -> str:
    if asset.changed:
        return (
            f"{current_name(asset)} ({asset.kind.value}) — {asset.localized_description} "
            f"(replaces {asset.name})"
        )
    return f"{asset.name} ({asset.kind.value}) — {asset.description}"


def to_shot_line(shot: CloneShot, names_by_asset_id: dict[str, str]) -> str:
    asset_names = [
        names_by_asset_id[asset_id] for asset_id in shot.asset_ids if asset_id in names_by_asset_id
    ]
    parts = [
        shot.id,
        format_timestamp(shot.at_ms),
        SHOT_SIZE_LABELS[shot.shot_size] if shot.shot_size else EMPTY_LABEL,
        CAMERA_ANGLE_LABELS[shot.camera_angle] if shot.camera_angle else EMPTY_LABEL,
        f"emotion: {shot.emotion or EMPTY_LABEL}",
        f"action: {shot.action or EMPTY_LABEL}",
        f"assets: {', '.join(asset_names) or EMPTY_LABEL}",
    ]
    return " · ".join(parts)
