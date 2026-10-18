from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from app.modules.films.film_files import FilmFiles
from app.modules.films.film_prompts import (
    THUMBNAIL_ASPECT,
    CharacterVoice,
    ClipPromptParts,
    build_clip_prompt,
    build_scene_image_prompt,
    build_thumbnail_prompt,
    pick_thumbnail_character_ids,
    to_character_aspect,
    to_project_aspect,
)
from app.modules.films.models import (
    Character,
    Episode,
    FilmProject,
    MediaStatus,
    Scene,
    Style,
    VoiceTemplate,
)
from app.modules.films.repository import FilmRepository
from app.modules.media_generation.models import GenerationKind, GenerationRequest
from app.modules.media_generation.service import (
    GenerationOrder,
    GenerationService,
    GenerationTargetIds,
)
from app.modules.media_generation.task_builder import (
    ASPECT_PARAM,
    CLIP_LENGTH_PARAM,
    CONSENT_CLIP_KEY,
    LANGUAGE_PARAM,
    MIN_LENGTH_PARAM,
    PROVIDER_VOICE_ID_PARAM,
    REFERENCE_KINDS_PARAM,
    REFERENCE_NAMES_PARAM,
    REFERENCES_KEY,
    SAMPLE_DURATION_PARAM,
    SAMPLE_TEXT_PARAM,
    SOURCE_IMAGE_KEY,
    START_FRAME_KEY,
    VOICE_NAME_PARAM,
    VOICE_SAMPLE_KEY,
)
from app.modules.providers.provider_catalog import MediaKind, ProviderId

CANDIDATE_PARAM = "candidate"
MS_PER_SECOND = 1000


@dataclass(frozen=True)
class SceneOrderContext:
    project: FilmProject
    episode_id: str
    scene: Scene


class FilmMediaQueue:
    def __init__(
        self,
        repository: FilmRepository,
        files: FilmFiles,
        generation_service: GenerationService,
        pick_speech_provider: Callable[[], ProviderId],
    ):
        self._repository = repository
        self._files = files
        self._generation_service = generation_service
        self._pick_speech_provider = pick_speech_provider

    def queue_character_image(
        self, project: FilmProject, character: Character, episode_id: str | None = None
    ) -> GenerationRequest:
        return self._generation_service.queue(
            GenerationOrder(
                kind=GenerationKind.CHARACTER_IMAGE,
                media_kind=MediaKind.IMAGE,
                prompt=character.image_prompt,
                target_ids=GenerationTargetIds(
                    project_id=project.id, episode_id=episode_id, character_id=character.id
                ),
                params={ASPECT_PARAM: to_character_aspect(character.entity_type)},
            )
        )

    def queue_character_edit(
        self, project: FilmProject, character: Character, prompt: str
    ) -> GenerationRequest:
        return self._generation_service.queue(
            GenerationOrder(
                kind=GenerationKind.EDIT_IMAGE,
                media_kind=MediaKind.EDIT_IMAGE,
                prompt=prompt,
                target_ids=GenerationTargetIds(project_id=project.id, character_id=character.id),
                input_paths={SOURCE_IMAGE_KEY: self._absolute(character.reference_path)},
                params={ASPECT_PARAM: to_character_aspect(character.entity_type)},
            )
        )

    def queue_scene_image(self, context: SceneOrderContext) -> GenerationRequest:
        style = self._find_style(context.project.style_id)
        return self._queue_scene_order(
            context,
            GenerationKind.SCENE_IMAGE,
            build_scene_image_prompt(style, context.scene.image_prompt),
            self._reference_inputs(context.scene.character_ids),
        )

    def queue_scene_edit(self, context: SceneOrderContext, prompt: str) -> GenerationRequest:
        inputs = self._reference_inputs(context.scene.character_ids)
        inputs.input_paths[SOURCE_IMAGE_KEY] = self._absolute(context.scene.image_path)
        return self._queue_scene_order(context, GenerationKind.EDIT_IMAGE, prompt, inputs)

    def queue_scene_clip(self, context: SceneOrderContext) -> GenerationRequest:
        project = context.project
        characters = self._repository.find_characters_by_ids(context.scene.character_ids)
        prompt = build_clip_prompt(
            ClipPromptParts(
                video_prompt=context.scene.video_prompt,
                allow_dialogue=project.allow_dialogue,
                voices=[
                    CharacterVoice(characters[cid].name, characters[cid].voice_description)
                    for cid in context.scene.character_ids
                    if cid in characters
                ],
            )
        )
        return self._generation_service.queue(
            GenerationOrder(
                kind=GenerationKind.SCENE_CLIP,
                media_kind=MediaKind.VIDEO,
                prompt=prompt,
                target_ids=self._scene_target_ids(context),
                input_paths={START_FRAME_KEY: self._absolute(context.scene.image_path)},
                params={
                    CLIP_LENGTH_PARAM: context.scene.clip_duration_s,
                    ASPECT_PARAM: to_project_aspect(project.orientation),
                },
            )
        )

    def queue_narration(
        self, context: SceneOrderContext, voice: VoiceTemplate
    ) -> GenerationRequest:
        provider_id = self._pick_speech_provider()
        input_paths: dict[str, Any] = {VOICE_SAMPLE_KEY: self._absolute(voice.sample_path)}
        if voice.consent_path:
            input_paths[CONSENT_CLIP_KEY] = self._absolute(voice.consent_path)
        params: dict[str, Any] = {
            VOICE_NAME_PARAM: voice.name,
            SAMPLE_DURATION_PARAM: voice.sample_duration_ms / MS_PER_SECOND,
            SAMPLE_TEXT_PARAM: voice.sample_text,
            LANGUAGE_PARAM: context.project.language.value,
        }
        provider_voice_id = (voice.provider_voices or {}).get(provider_id.value)
        if provider_voice_id:
            params[PROVIDER_VOICE_ID_PARAM] = provider_voice_id
        return self._generation_service.queue(
            GenerationOrder(
                kind=GenerationKind.NARRATION,
                media_kind=MediaKind.SPEECH,
                prompt=context.scene.narrator_text or "",
                target_ids=self._scene_target_ids(context),
                input_paths=input_paths,
                params=params,
            )
        )

    def queue_music(
        self, project: FilmProject, episode: Episode, min_length_s: int
    ) -> GenerationRequest:
        return self._generation_service.queue(
            GenerationOrder(
                kind=GenerationKind.MUSIC,
                media_kind=MediaKind.MUSIC,
                prompt=episode.music_prompt or "",
                target_ids=GenerationTargetIds(project_id=project.id, episode_id=episode.id),
                params={MIN_LENGTH_PARAM: min_length_s},
            )
        )

    def queue_thumbnail(
        self, project: FilmProject, episode: Episode, scenes: Sequence[Scene], candidate: int
    ) -> GenerationRequest:
        style = self._find_style(project.style_id)
        inputs = self._reference_inputs(pick_thumbnail_character_ids(scenes))
        return self._generation_service.queue(
            GenerationOrder(
                kind=GenerationKind.THUMBNAIL,
                media_kind=MediaKind.IMAGE,
                prompt=build_thumbnail_prompt(style, episode.thumbnail_prompt or ""),
                target_ids=GenerationTargetIds(project_id=project.id, episode_id=episode.id),
                input_paths=inputs.input_paths,
                params={
                    **inputs.params,
                    ASPECT_PARAM: THUMBNAIL_ASPECT,
                    CANDIDATE_PARAM: candidate,
                },
            )
        )

    def _queue_scene_order(
        self,
        context: SceneOrderContext,
        kind: GenerationKind,
        prompt: str,
        inputs: "_ReferenceInputs",
    ) -> GenerationRequest:
        media_kind = MediaKind.IMAGE if kind is GenerationKind.SCENE_IMAGE else MediaKind.EDIT_IMAGE
        return self._generation_service.queue(
            GenerationOrder(
                kind=kind,
                media_kind=media_kind,
                prompt=prompt,
                target_ids=self._scene_target_ids(context),
                input_paths=inputs.input_paths,
                params={
                    **inputs.params,
                    ASPECT_PARAM: to_project_aspect(context.project.orientation),
                },
            )
        )

    def _reference_inputs(self, character_ids: Sequence[str]) -> "_ReferenceInputs":
        characters_by_id = self._repository.find_characters_by_ids(character_ids)
        characters = [
            characters_by_id[character_id]
            for character_id in dict.fromkeys(character_ids)
            if character_id in characters_by_id
            and characters_by_id[character_id].reference_status is MediaStatus.DONE
            and characters_by_id[character_id].reference_path
        ]
        return _ReferenceInputs(
            input_paths={
                REFERENCES_KEY: [
                    self._absolute(character.reference_path) for character in characters
                ]
            },
            params={
                REFERENCE_NAMES_PARAM: [character.name for character in characters],
                REFERENCE_KINDS_PARAM: [character.entity_type.value for character in characters],
            },
        )

    def _scene_target_ids(self, context: SceneOrderContext) -> GenerationTargetIds:
        return GenerationTargetIds(
            project_id=context.project.id,
            episode_id=context.episode_id,
            scene_id=context.scene.id,
        )

    def _find_style(self, style_id: str) -> Style:
        style = self._repository.find_style(style_id)
        if style is None:
            raise LookupError(style_id)
        return style

    def _absolute(self, relative_path: str | None) -> str:
        return str(self._files.to_absolute(relative_path or ""))


@dataclass(frozen=True)
class _ReferenceInputs:
    input_paths: dict[str, Any]
    params: dict[str, Any]
