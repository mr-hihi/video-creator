import logging
import re
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol
from uuid import uuid4

from app.common.process import CommandError
from app.modules.films.errors import FilmConflictError, InvalidFilmRequestError, VoiceNotFoundError
from app.modules.films.field_rules import CLEARED_TEXT, to_optional_text, to_valid_changes
from app.modules.films.film_files import FilmFiles
from app.modules.films.models import VoiceTemplate
from app.modules.films.repository import FilmRepository
from app.modules.films.upload_rules import (
    AUDIO_UPLOAD,
    FileUpload,
    build_too_large_message,
    to_upload_extension,
)
from app.modules.jobs.video_to_markdown.transcript import Transcript, join_segment_texts
from app.modules.providers.provider_catalog import ProviderId

logger = logging.getLogger(__name__)

VOICE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
VOICE_DESCRIPTION_LIMIT = 300
MIN_SAMPLE_DURATION_MS = 3_000
MAX_SAMPLE_DURATION_MS = 180_000
TRANSCRIPTION_LANGUAGE = "auto"
TRANSCRIPTION_AUDIO_NAME = "sample.wav"
CONSENT_PROVIDER_ID = ProviderId.GOOGLE
VOICE_NAME_MESSAGE = "Voice name must be 1-64 letters, digits, '-' or '_'"
VOICE_DESCRIPTION_MESSAGE = f"Description must be at most {VOICE_DESCRIPTION_LIMIT} characters"
DUPLICATE_VOICE_MESSAGE = "A voice named '{name}' already exists"
SAMPLE_DURATION_MESSAGE = "Voice sample must be 3-180 seconds long"
UNREADABLE_SAMPLE_MESSAGE = "Could not read the voice sample"
UNTRANSCRIBED_SAMPLE_MESSAGE = "Could not transcribe the sample. Type its text instead"
BLANK_SAMPLE_TEXT_MESSAGE = "Sample text must not be blank"
VOICE_IN_USE_MESSAGE = "Voice '{name}' is the narrator of {count} project(s)"


class SampleMedia(Protocol):
    def probe_duration_ms(self, video_path: Path) -> int: ...

    def extract_audio(self, video_path: Path, audio_path: Path) -> Path: ...


class SampleTranscriber(Protocol):
    def transcribe(self, audio_path: Path, language: str) -> Transcript: ...


def to_sample_text(sample_text: str) -> str:
    text = sample_text.strip()
    if not text:
        raise InvalidFilmRequestError(BLANK_SAMPLE_TEXT_MESSAGE)
    return text


VOICE_CHANGE_RULES = {
    "sample_text": to_sample_text,
    "description": partial(
        to_optional_text, limit=VOICE_DESCRIPTION_LIMIT, message=VOICE_DESCRIPTION_MESSAGE
    ),
}


@dataclass(frozen=True)
class VoiceDraft:
    name: str
    sample: FileUpload
    sample_text: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class VoiceChanges:
    name: str | None = None
    sample_text: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class FilmVoiceTools:
    repository: FilmRepository
    files: FilmFiles
    media: SampleMedia
    transcriber: SampleTranscriber


class FilmVoiceService:
    def __init__(self, tools: FilmVoiceTools):
        self._repository = tools.repository
        self._files = tools.files
        self._media = tools.media
        self._transcriber = tools.transcriber

    def list_voices(self) -> list[VoiceTemplate]:
        return self._repository.find_voices()

    def create_voice(self, draft: VoiceDraft) -> VoiceTemplate:
        voice_id = str(uuid4())
        name = self._to_free_name(draft.name, voice_id)
        description = to_optional_text(
            draft.description, VOICE_DESCRIPTION_LIMIT, VOICE_DESCRIPTION_MESSAGE
        )
        extension = to_upload_extension(draft.sample.filename, AUDIO_UPLOAD)
        try:
            sample_path = self._save_audio(
                draft.sample, self._files.voice_sample_path(voice_id, extension)
            )
            voice = VoiceTemplate(
                id=voice_id,
                name=name,
                description=description,
                sample_path=self._files.to_relative(sample_path),
                sample_duration_ms=self._probe_sample_duration_ms(sample_path),
                sample_text=self._read_sample_text(draft.sample_text, sample_path),
                consent_path=None,
                provider_voices={},
            )
            return self._repository.add_voice(voice)
        except Exception:
            self._files.delete_dir(self._files.voice_dir(voice_id))
            raise

    def update_voice(self, voice_id: str, changes: VoiceChanges) -> VoiceTemplate:
        voice = self._get_voice(voice_id)
        values: dict[str, Any] = to_valid_changes(changes, VOICE_CHANGE_RULES)
        if changes.name is not None:
            values["name"] = self._to_free_name(changes.name, voice.id)
        if values:
            self._repository.update_voice(voice.id, values)
        return self._get_voice(voice.id)

    def delete_voice(self, voice_id: str) -> None:
        voice = self._get_voice(voice_id)
        project_count = self._repository.count_projects_with_narrator(voice.id)
        if project_count > 0:
            raise FilmConflictError(
                VOICE_IN_USE_MESSAGE.format(name=voice.name, count=project_count)
            )
        self._repository.delete_voice(voice.id)
        self._files.delete_dir(self._files.voice_dir(voice.id))

    def upload_consent(self, voice_id: str, upload: FileUpload) -> VoiceTemplate:
        voice = self._get_voice(voice_id)
        extension = to_upload_extension(upload.filename, AUDIO_UPLOAD)
        consent_path = self._save_audio(upload, self._files.voice_consent_path(voice.id, extension))
        self._repository.update_voice(
            voice.id,
            {
                "consent_path": self._files.to_relative(consent_path),
                "provider_voices": _without_consent_copy(voice.provider_voices),
            },
        )
        return self._get_voice(voice.id)

    def delete_consent(self, voice_id: str) -> None:
        voice = self._get_voice(voice_id)
        self._files.delete(voice.consent_path)
        self._repository.update_voice(
            voice.id,
            {
                "consent_path": None,
                "provider_voices": _without_consent_copy(voice.provider_voices),
            },
        )

    def _save_audio(self, upload: FileUpload, destination: Path) -> Path:
        too_large_message = build_too_large_message(AUDIO_UPLOAD, self._files.max_upload_mb)
        return self._files.save_upload(upload.stream, destination, too_large_message)

    def _probe_sample_duration_ms(self, sample_path: Path) -> int:
        try:
            duration_ms = self._media.probe_duration_ms(sample_path)
        except CommandError as error:
            logger.warning(
                "Voice sample %s could not be probed: %s",
                self._files.to_relative(sample_path),
                error,
            )
            raise InvalidFilmRequestError(UNREADABLE_SAMPLE_MESSAGE) from error
        if not MIN_SAMPLE_DURATION_MS <= duration_ms <= MAX_SAMPLE_DURATION_MS:
            raise InvalidFilmRequestError(SAMPLE_DURATION_MESSAGE)
        return duration_ms

    def _read_sample_text(self, sample_text: str | None, sample_path: Path) -> str:
        typed_text = (sample_text or CLEARED_TEXT).strip()
        if typed_text:
            return typed_text
        try:
            transcript = self._transcribe(sample_path)
        except CommandError as error:
            logger.warning(
                "Voice sample %s could not be transcribed: %s",
                self._files.to_relative(sample_path),
                error,
            )
            raise InvalidFilmRequestError(UNTRANSCRIBED_SAMPLE_MESSAGE) from error
        transcribed_text = join_segment_texts(transcript.segments)
        if not transcribed_text:
            raise InvalidFilmRequestError(UNTRANSCRIBED_SAMPLE_MESSAGE)
        return transcribed_text

    def _transcribe(self, sample_path: Path) -> Transcript:
        with TemporaryDirectory() as work_dir:
            audio_path = self._media.extract_audio(
                sample_path, Path(work_dir) / TRANSCRIPTION_AUDIO_NAME
            )
            return self._transcriber.transcribe(audio_path, TRANSCRIPTION_LANGUAGE)

    def _get_voice(self, voice_id: str) -> VoiceTemplate:
        voice = self._repository.find_voice(voice_id)
        if voice is None:
            raise VoiceNotFoundError(voice_id)
        return voice

    def _to_free_name(self, requested_name: str, own_voice_id: str) -> str:
        name = requested_name.strip()
        if not VOICE_NAME_PATTERN.fullmatch(name):
            raise InvalidFilmRequestError(VOICE_NAME_MESSAGE)
        existing = self._repository.find_voice_by_name(name)
        if existing is not None and existing.id != own_voice_id:
            raise FilmConflictError(DUPLICATE_VOICE_MESSAGE.format(name=name))
        return name


def _without_consent_copy(provider_voices: dict[str, Any]) -> dict[str, Any]:
    return {
        provider_id: provider_voice_id
        for provider_id, provider_voice_id in provider_voices.items()
        if provider_id != CONSENT_PROVIDER_ID
    }
