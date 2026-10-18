from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request, UploadFile, status

from app.modules.films.character_service import (
    CharacterChanges,
    CharacterDraft,
    FilmCharacterService,
)
from app.modules.films.models import EntityType
from app.modules.films.request_values import to_patch_values
from app.modules.films.schemas import (
    CharacterDetailResponse,
    CharacterResponse,
    CreateCharacterRequest,
    CreateStyleRequest,
    StyleResponse,
    UpdateCharacterRequest,
    UpdateStyleRequest,
    UpdateVoiceRequest,
    VoiceResponse,
)
from app.modules.films.style_service import FilmStyleService, StyleChanges, StyleDraft
from app.modules.films.upload_rules import FileUpload
from app.modules.films.voice_service import FilmVoiceService, VoiceChanges, VoiceDraft

CLEARABLE_CHARACTER_FIELDS = frozenset({"voice_description"})
CLEARABLE_STYLE_FIELDS = frozenset({"negative_prompt", "scene_prefix", "lighting"})
CLEARABLE_VOICE_FIELDS = frozenset({"description"})

router = APIRouter(prefix="/films", tags=["films"])


def get_film_character_service(request: Request) -> FilmCharacterService:
    return request.app.state.container.film_character_service


def get_film_style_service(request: Request) -> FilmStyleService:
    return request.app.state.container.film_style_service


def get_film_voice_service(request: Request) -> FilmVoiceService:
    return request.app.state.container.film_voice_service


CharacterServiceDependency = Annotated[FilmCharacterService, Depends(get_film_character_service)]
StyleServiceDependency = Annotated[FilmStyleService, Depends(get_film_style_service)]
VoiceServiceDependency = Annotated[FilmVoiceService, Depends(get_film_voice_service)]


def to_file_upload(file: UploadFile) -> FileUpload:
    return FileUpload(filename=file.filename or "", stream=file.file)


@router.get("/characters")
def list_characters(
    service: CharacterServiceDependency,
    entity_type: Annotated[EntityType | None, Query(alias="type")] = None,
    q: str = "",
) -> list[CharacterResponse]:
    return [
        CharacterResponse.from_summary(summary)
        for summary in service.list_characters(entity_type, q)
    ]


@router.post("/characters", status_code=status.HTTP_201_CREATED)
def create_character(
    body: CreateCharacterRequest, service: CharacterServiceDependency
) -> CharacterResponse:
    return CharacterResponse.from_summary(
        service.create_character(CharacterDraft(**body.model_dump()))
    )


@router.get("/characters/{character_id}")
def get_character(
    character_id: str, service: CharacterServiceDependency
) -> CharacterDetailResponse:
    return CharacterDetailResponse.from_detail(service.get_character(character_id))


@router.patch("/characters/{character_id}")
def update_character(
    character_id: str, body: UpdateCharacterRequest, service: CharacterServiceDependency
) -> CharacterResponse:
    changes = CharacterChanges(**to_patch_values(body, CLEARABLE_CHARACTER_FIELDS))
    return CharacterResponse.from_summary(service.update_character(character_id, changes))


@router.delete("/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_character(character_id: str, service: CharacterServiceDependency) -> None:
    service.delete_character(character_id)


@router.post("/characters/{character_id}/reference")
def upload_reference(
    character_id: str, file: UploadFile, service: CharacterServiceDependency
) -> CharacterResponse:
    return CharacterResponse.from_summary(
        service.upload_reference(character_id, to_file_upload(file))
    )


@router.get("/styles")
def list_styles(service: StyleServiceDependency) -> list[StyleResponse]:
    return [StyleResponse.model_validate(style) for style in service.list_styles()]


@router.post("/styles", status_code=status.HTTP_201_CREATED)
def create_style(body: CreateStyleRequest, service: StyleServiceDependency) -> StyleResponse:
    return StyleResponse.model_validate(service.create_style(StyleDraft(**body.model_dump())))


@router.patch("/styles/{style_id}")
def update_style(
    style_id: str, body: UpdateStyleRequest, service: StyleServiceDependency
) -> StyleResponse:
    changes = StyleChanges(**to_patch_values(body, CLEARABLE_STYLE_FIELDS))
    return StyleResponse.model_validate(service.update_style(style_id, changes))


@router.delete("/styles/{style_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_style(style_id: str, service: StyleServiceDependency) -> None:
    service.delete_style(style_id)


@router.get("/voices")
def list_voices(service: VoiceServiceDependency) -> list[VoiceResponse]:
    return [VoiceResponse.model_validate(voice) for voice in service.list_voices()]


@router.post("/voices", status_code=status.HTTP_201_CREATED)
def create_voice(
    file: UploadFile,
    name: Annotated[str, Form()],
    service: VoiceServiceDependency,
    sample_text: Annotated[str | None, Form(alias="sampleText")] = None,
    description: Annotated[str | None, Form()] = None,
) -> VoiceResponse:
    draft = VoiceDraft(
        name=name,
        sample=to_file_upload(file),
        sample_text=sample_text,
        description=description,
    )
    return VoiceResponse.model_validate(service.create_voice(draft))


@router.patch("/voices/{voice_id}")
def update_voice(
    voice_id: str, body: UpdateVoiceRequest, service: VoiceServiceDependency
) -> VoiceResponse:
    changes = VoiceChanges(**to_patch_values(body, CLEARABLE_VOICE_FIELDS))
    return VoiceResponse.model_validate(service.update_voice(voice_id, changes))


@router.delete("/voices/{voice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_voice(voice_id: str, service: VoiceServiceDependency) -> None:
    service.delete_voice(voice_id)


@router.post("/voices/{voice_id}/consent")
def upload_consent(
    voice_id: str, file: UploadFile, service: VoiceServiceDependency
) -> VoiceResponse:
    return VoiceResponse.model_validate(service.upload_consent(voice_id, to_file_upload(file)))


@router.delete("/voices/{voice_id}/consent", status_code=status.HTTP_204_NO_CONTENT)
def delete_consent(voice_id: str, service: VoiceServiceDependency) -> None:
    service.delete_consent(voice_id)
