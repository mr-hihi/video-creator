from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.db import utc_now
from app.modules.films.film_files import FilmFiles
from app.modules.films.media_queue import CANDIDATE_PARAM
from app.modules.films.models import (
    OPEN_MEDIA_STATUSES,
    Episode,
    EpisodeStatus,
    MediaStatus,
    ReferenceSource,
    Scene,
    SceneImageSource,
)
from app.modules.films.repository import FilmRepository
from app.modules.films.scene_resets import NEW_CLIP_RESET, NEW_IMAGE_RESET
from app.modules.media_generation.models import GenerationKind, GenerationRequest, GenerationStatus
from app.modules.media_generation.repository import GenerationRequestRepository
from app.modules.media_generation.task_builder import PROVIDER_VOICE_ID_PARAM
from app.modules.providers.provider_catalog import ProviderId

MISSING_REFERENCE_MESSAGE = "Reference image missing for: {names}"
COPIED_VOICE_PROVIDERS = frozenset({ProviderId.ELEVENLABS, ProviderId.GOOGLE})

RequestListener = Callable[[GenerationRequest], None]
ScenePathBuilder = Callable[[str, str, str, str], Path]


class DurationProbe(Protocol):
    def probe_duration_ms(self, video_path: Path) -> int: ...


@dataclass(frozen=True)
class FilmTargetTools:
    repository: FilmRepository
    files: FilmFiles
    request_repository: GenerationRequestRepository
    duration_probe: DurationProbe
    on_final: RequestListener


class _FilmTarget:
    def __init__(self, tools: FilmTargetTools):
        self._tools = tools

    def is_ready(self, request: GenerationRequest) -> bool:
        return True

    def on_final(self, request: GenerationRequest) -> None:
        self._tools.on_final(request)

    def _flag_assembly(self, episode_id: str | None) -> None:
        episode = self._find_episode(episode_id)
        if episode is not None and episode.status is EpisodeStatus.DONE:
            self._tools.repository.update_episode(episode.id, {"needs_assembly": True})

    def _find_episode(self, episode_id: str | None) -> Episode | None:
        return None if episode_id is None else self._tools.repository.find_episode(episode_id)

    def _find_scene(self, request: GenerationRequest) -> Scene | None:
        return self._tools.repository.find_scene(request.scene_id or "")

    def _scene_path(
        self, request: GenerationRequest, build_path: ScenePathBuilder, ext: str
    ) -> Path:
        return build_path(
            request.project_id or "", request.episode_id or "", request.scene_id or "", ext
        )


class CharacterReferenceTarget(_FilmTarget):
    def mark_queued(self, request: GenerationRequest) -> None:
        self._set_status(request, MediaStatus.QUEUED)

    def mark_processing(self, request: GenerationRequest) -> None:
        self._set_status(request, MediaStatus.PROCESSING)

    def output_path(self, request: GenerationRequest, file_extension: str) -> Path:
        return self._tools.files.character_reference_path(
            request.character_id or "", file_extension
        )

    def save_result(self, request: GenerationRequest, file_path: Path) -> None:
        self._tools.files.keep_only(file_path)
        source = (
            ReferenceSource.EDITED
            if request.kind is GenerationKind.EDIT_IMAGE
            else ReferenceSource.GENERATED
        )
        self._tools.repository.update_character(
            request.character_id or "",
            {
                "reference_status": MediaStatus.DONE,
                "reference_source": source,
                "reference_path": self._tools.files.to_relative(file_path),
                "reference_error": None,
                "provider_media": None,
            },
        )

    def mark_failed(self, request: GenerationRequest, error_message: str) -> None:
        character = self._tools.repository.find_character(request.character_id or "")
        if character is None:
            return
        status = MediaStatus.DONE if character.reference_path else MediaStatus.FAILED
        self._tools.repository.update_character(
            character.id, {"reference_status": status, "reference_error": error_message}
        )

    def mark_cancelled(self, request: GenerationRequest) -> None:
        character = self._tools.repository.find_character(request.character_id or "")
        if character is None:
            return
        status = MediaStatus.DONE if character.reference_path else MediaStatus.NONE
        self._tools.repository.update_character(character.id, {"reference_status": status})

    def _set_status(self, request: GenerationRequest, status: MediaStatus) -> None:
        self._tools.repository.update_character(
            request.character_id or "", {"reference_status": status}
        )


@dataclass(frozen=True)
class SceneMedia:
    status_field: str
    path_field: str
    error_field: str


SCENE_IMAGE_MEDIA = SceneMedia("image_status", "image_path", "image_error")
SCENE_CLIP_MEDIA = SceneMedia("clip_status", "clip_path", "clip_error")
SCENE_NARRATION_MEDIA = SceneMedia("narration_status", "narration_path", "narration_error")


class _SceneMediaTarget(_FilmTarget):
    media: SceneMedia

    def mark_queued(self, request: GenerationRequest) -> None:
        self._set_status(request, MediaStatus.QUEUED)

    def mark_processing(self, request: GenerationRequest) -> None:
        self._set_status(request, MediaStatus.PROCESSING)

    def mark_failed(self, request: GenerationRequest, error_message: str) -> None:
        scene = self._find_scene(request)
        if scene is None:
            return
        status = MediaStatus.DONE if getattr(scene, self.media.path_field) else MediaStatus.FAILED
        self._tools.repository.update_scene(
            scene.id, {self.media.status_field: status, self.media.error_field: error_message}
        )

    def mark_cancelled(self, request: GenerationRequest) -> None:
        scene = self._find_scene(request)
        if scene is None:
            return
        status = MediaStatus.DONE if getattr(scene, self.media.path_field) else MediaStatus.NONE
        self._tools.repository.update_scene(scene.id, {self.media.status_field: status})

    def _save_scene_file(
        self, request: GenerationRequest, file_path: Path, extra_values: Mapping[str, Any]
    ) -> None:
        self._tools.files.keep_only(file_path)
        self._tools.repository.update_scene(
            request.scene_id or "",
            {
                self.media.status_field: MediaStatus.DONE,
                self.media.path_field: self._tools.files.to_relative(file_path),
                self.media.error_field: None,
                **extra_values,
            },
        )
        self._flag_assembly(request.episode_id)

    def _set_status(self, request: GenerationRequest, status: MediaStatus) -> None:
        self._tools.repository.update_scene(
            request.scene_id or "", {self.media.status_field: status}
        )


class SceneImageTarget(_SceneMediaTarget):
    media = SCENE_IMAGE_MEDIA

    def is_ready(self, request: GenerationRequest) -> bool:
        if request.kind is not GenerationKind.SCENE_IMAGE:
            return True
        scene = self._find_scene(request)
        if scene is None:
            return True
        characters = self._tools.repository.find_characters_by_ids(scene.character_ids)
        missing_names = [
            characters[character_id].name
            for character_id in scene.character_ids
            if character_id in characters
            and characters[character_id].reference_status is not MediaStatus.DONE
        ]
        if not missing_names:
            return True
        self._fail_unsubmitted(
            request, MISSING_REFERENCE_MESSAGE.format(names=", ".join(missing_names))
        )
        return False

    def output_path(self, request: GenerationRequest, file_extension: str) -> Path:
        return self._scene_path(request, self._tools.files.scene_image_path, file_extension)

    def save_result(self, request: GenerationRequest, file_path: Path) -> None:
        scene = self._find_scene(request)
        if scene is None:
            return
        self._tools.files.delete(scene.clip_path)
        self._tools.files.delete_dir(
            self._tools.files.scene_clip_segments_dir(
                request.project_id or "", request.episode_id or "", scene.id
            )
        )
        source = (
            SceneImageSource.EDITED
            if request.kind is GenerationKind.EDIT_IMAGE
            else SceneImageSource.GENERATED
        )
        reset = (
            {**NEW_IMAGE_RESET, "clip_status": scene.clip_status}
            if scene.clip_status in OPEN_MEDIA_STATUSES
            else NEW_IMAGE_RESET
        )
        self._save_scene_file(request, file_path, {**reset, "image_source": source})

    def _fail_unsubmitted(self, request: GenerationRequest, error_message: str) -> None:
        self._tools.request_repository.update_fields(
            request.id,
            {
                "status": GenerationStatus.FAILED,
                "error_message": error_message,
                "finished_at": utc_now(),
            },
        )
        failed = self._tools.request_repository.find_by_id(request.id) or request
        self.mark_failed(failed, error_message)
        self.on_final(failed)


class SceneClipTarget(_SceneMediaTarget):
    media = SCENE_CLIP_MEDIA

    def is_ready(self, request: GenerationRequest) -> bool:
        scene = self._find_scene(request)
        return scene is None or scene.image_status is MediaStatus.DONE

    def output_path(self, request: GenerationRequest, file_extension: str) -> Path:
        return self._scene_path(request, self._tools.files.scene_clip_path, file_extension)

    def save_result(self, request: GenerationRequest, file_path: Path) -> None:
        duration_ms = self._tools.duration_probe.probe_duration_ms(file_path)
        self._save_scene_file(
            request, file_path, {**NEW_CLIP_RESET, "clip_duration_ms": duration_ms}
        )


class NarrationTarget(_SceneMediaTarget):
    media = SCENE_NARRATION_MEDIA

    def output_path(self, request: GenerationRequest, file_extension: str) -> Path:
        return self._scene_path(request, self._tools.files.scene_narration_path, file_extension)

    def save_result(self, request: GenerationRequest, file_path: Path) -> None:
        duration_ms = self._tools.duration_probe.probe_duration_ms(file_path)
        self._save_scene_file(request, file_path, {"narration_duration_ms": duration_ms})
        self._remember_voice_copy(request)

    def _remember_voice_copy(self, request: GenerationRequest) -> None:
        provider_voice_id = request.params.get(PROVIDER_VOICE_ID_PARAM)
        if not provider_voice_id or request.provider not in COPIED_VOICE_PROVIDERS:
            return
        project = self._tools.repository.find_project(request.project_id or "")
        if project is None or project.narrator_voice_id is None:
            return
        voice = self._tools.repository.find_voice(project.narrator_voice_id)
        if voice is None or (voice.provider_voices or {}).get(request.provider):
            return
        self._tools.repository.update_voice(
            voice.id,
            {
                "provider_voices": {
                    **(voice.provider_voices or {}),
                    request.provider: provider_voice_id,
                }
            },
        )


class MusicTarget(_FilmTarget):
    def mark_queued(self, request: GenerationRequest) -> None:
        self._set_status(request, MediaStatus.QUEUED)

    def mark_processing(self, request: GenerationRequest) -> None:
        self._set_status(request, MediaStatus.PROCESSING)

    def output_path(self, request: GenerationRequest, file_extension: str) -> Path:
        return self._tools.files.music_path(
            request.project_id or "", request.episode_id or "", file_extension
        )

    def save_result(self, request: GenerationRequest, file_path: Path) -> None:
        self._tools.files.keep_only(file_path)
        self._tools.repository.update_episode(
            request.episode_id or "",
            {
                "music_status": MediaStatus.DONE,
                "music_path": self._tools.files.to_relative(file_path),
                "music_error": None,
            },
        )

    def mark_failed(self, request: GenerationRequest, error_message: str) -> None:
        episode = self._find_episode(request.episode_id)
        if episode is None:
            return
        status = MediaStatus.DONE if episode.music_path else MediaStatus.FAILED
        self._tools.repository.update_episode(
            episode.id, {"music_status": status, "music_error": error_message}
        )

    def mark_cancelled(self, request: GenerationRequest) -> None:
        episode = self._find_episode(request.episode_id)
        if episode is None:
            return
        status = MediaStatus.DONE if episode.music_path else MediaStatus.NONE
        self._tools.repository.update_episode(episode.id, {"music_status": status})

    def _set_status(self, request: GenerationRequest, status: MediaStatus) -> None:
        self._tools.repository.update_episode(request.episode_id or "", {"music_status": status})


class ThumbnailTarget(_FilmTarget):
    def mark_queued(self, request: GenerationRequest) -> None:
        return None

    def mark_processing(self, request: GenerationRequest) -> None:
        return None

    def output_path(self, request: GenerationRequest, file_extension: str) -> Path:
        return self._tools.files.thumbnail_candidate_path(
            request.project_id or "",
            request.episode_id or "",
            int(request.params.get(CANDIDATE_PARAM, 1)),
            file_extension,
        )

    def save_result(self, request: GenerationRequest, file_path: Path) -> None:
        self._tools.files.keep_only(file_path)

    def mark_failed(self, request: GenerationRequest, error_message: str) -> None:
        return None

    def mark_cancelled(self, request: GenerationRequest) -> None:
        return None

    def on_final(self, request: GenerationRequest) -> None:
        return None


class EditImageTarget:
    def __init__(self, character_target: CharacterReferenceTarget, scene_target: SceneImageTarget):
        self._character_target = character_target
        self._scene_target = scene_target

    def mark_queued(self, request: GenerationRequest) -> None:
        self._pick(request).mark_queued(request)

    def is_ready(self, request: GenerationRequest) -> bool:
        return self._pick(request).is_ready(request)

    def mark_processing(self, request: GenerationRequest) -> None:
        self._pick(request).mark_processing(request)

    def output_path(self, request: GenerationRequest, file_extension: str) -> Path:
        return self._pick(request).output_path(request, file_extension)

    def save_result(self, request: GenerationRequest, file_path: Path) -> None:
        self._pick(request).save_result(request, file_path)

    def mark_failed(self, request: GenerationRequest, error_message: str) -> None:
        self._pick(request).mark_failed(request, error_message)

    def mark_cancelled(self, request: GenerationRequest) -> None:
        self._pick(request).mark_cancelled(request)

    def on_final(self, request: GenerationRequest) -> None:
        self._pick(request).on_final(request)

    def _pick(self, request: GenerationRequest) -> CharacterReferenceTarget | SceneImageTarget:
        if request.scene_id is not None:
            return self._scene_target
        return self._character_target


def build_film_targets(tools: FilmTargetTools) -> dict[GenerationKind, Any]:
    character_target = CharacterReferenceTarget(tools)
    scene_image_target = SceneImageTarget(tools)
    return {
        GenerationKind.CHARACTER_IMAGE: character_target,
        GenerationKind.SCENE_IMAGE: scene_image_target,
        GenerationKind.EDIT_IMAGE: EditImageTarget(character_target, scene_image_target),
        GenerationKind.SCENE_CLIP: SceneClipTarget(tools),
        GenerationKind.NARRATION: NarrationTarget(tools),
        GenerationKind.MUSIC: MusicTarget(tools),
        GenerationKind.THUMBNAIL: ThumbnailTarget(tools),
    }
