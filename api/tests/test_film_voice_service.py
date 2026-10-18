import io
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.common.process import CommandError
from app.modules.films.errors import (
    FilmConflictError,
    FilmFileTooLargeError,
    InvalidFilmRequestError,
    VoiceNotFoundError,
)
from app.modules.films.film_files import FilmFiles
from app.modules.films.models import VoiceTemplate
from app.modules.films.repository import FilmRepository
from app.modules.films.upload_rules import FileUpload
from app.modules.films.voice_service import (
    FilmVoiceService,
    FilmVoiceTools,
    VoiceChanges,
    VoiceDraft,
)
from app.modules.jobs.video_to_markdown.ffmpeg_media import FfmpegMediaProcessor
from app.modules.jobs.video_to_markdown.transcript import Transcript, TranscriptSegment
from app.modules.jobs.video_to_markdown.whisper_transcriber import WhisperCppTranscriber

MAX_UPLOAD_MB = 1
NEW_VOICE_ID = "voice-new"
SAMPLE_DURATION_MS = 12_000
NARRATOR = VoiceTemplate(
    id="vt-1",
    name="narrator-en",
    description="Warm narrator",
    sample_path="voices/vt-1/sample.wav",
    sample_text="Hello there",
    sample_duration_ms=SAMPLE_DURATION_MS,
    consent_path="voices/vt-1/consent.wav",
    provider_voices={"elevenlabs": "el-1", "google": "g-1"},
)
SPOKEN_TRANSCRIPT = Transcript(
    language="en",
    segments=[
        TranscriptSegment(start_ms=0, end_ms=2000, text=" Solar warning"),
        TranscriptSegment(start_ms=2000, end_ms=4000, text=" for the coast. "),
    ],
)


def build_voices(tmp_path, monkeypatch, voices=(NARRATOR,), **arrangement):
    monkeypatch.setattr("app.modules.films.voice_service.uuid4", lambda: NEW_VOICE_ID)
    voices_by_id = {voice.id: voice for voice in voices}
    repository = MagicMock(spec=FilmRepository)
    repository.find_voice.side_effect = voices_by_id.get
    repository.find_voice_by_name.side_effect = lambda name: next(
        (voice for voice in voices if voice.name.casefold() == name.casefold()), None
    )
    repository.find_voices.return_value = list(voices)
    repository.add_voice.side_effect = lambda voice: voice
    repository.count_projects_with_narrator.return_value = arrangement.get("narrator_count", 0)
    media = MagicMock(spec=FfmpegMediaProcessor)
    media.probe_duration_ms.side_effect = arrangement.get("durations", [SAMPLE_DURATION_MS])
    media.extract_audio.side_effect = lambda sample_path, audio_path: audio_path
    transcriber = MagicMock(spec=WhisperCppTranscriber)
    transcriber.transcribe.side_effect = arrangement.get("transcripts", [SPOKEN_TRANSCRIPT])
    files = FilmFiles(tmp_path, MAX_UPLOAD_MB)
    service = FilmVoiceService(
        FilmVoiceTools(repository=repository, files=files, media=media, transcriber=transcriber)
    )
    return SimpleNamespace(
        service=service,
        repository=repository,
        files=files,
        media=media,
        transcriber=transcriber,
    )


def capture(error_class, call):
    with pytest.raises(error_class) as caught:
        call()
    return caught.value


def build_draft(**overrides) -> VoiceDraft:
    fields = {
        "name": " narrator-auto ",
        "sample": FileUpload("Sample.WAV", io.BytesIO(b"RIFF")),
    }
    return VoiceDraft(**{**fields, **overrides})


def create_failing(voices, draft, error_class):
    error = capture(error_class, lambda: voices.service.create_voice(draft))
    return SimpleNamespace(
        message=str(error), is_folder_left=voices.files.voice_dir(NEW_VOICE_ID).exists()
    )


@pytest.fixture
def listed_voices(tmp_path, monkeypatch):
    return build_voices(tmp_path, monkeypatch).service.list_voices()


@pytest.fixture
def typed_voice(tmp_path, monkeypatch):
    voices = build_voices(tmp_path, monkeypatch)
    voice = voices.service.create_voice(
        build_draft(sample_text="  Typed words  ", description=" Calm ")
    )
    return SimpleNamespace(
        voice=voice,
        transcriber=voices.transcriber,
        stored_bytes=voices.files.voice_sample_path(NEW_VOICE_ID, "wav").read_bytes(),
    )


@pytest.fixture
def transcribed_voice(tmp_path, monkeypatch):
    voices = build_voices(tmp_path, monkeypatch)
    voice = voices.service.create_voice(build_draft(sample_text="   "))
    extract_args = voices.media.extract_audio.call_args.args
    return SimpleNamespace(
        voice=voice,
        extract_source=voices.files.to_relative(extract_args[0]),
        extract_target_name=extract_args[1].name,
        is_work_folder_left=extract_args[1].parent.exists(),
        transcribe_language=voices.transcriber.transcribe.call_args.args[1],
    )


@pytest.fixture(params=[[Transcript(language="en", segments=[])], CommandError("whisper failed")])
def untranscribed_outcome(request, tmp_path, monkeypatch):
    voices = build_voices(tmp_path, monkeypatch, transcripts=request.param)
    return create_failing(voices, build_draft(), InvalidFilmRequestError)


@pytest.fixture(
    params=[
        (build_draft(name="bad name"), "Voice name must be 1-64 letters, digits, '-' or '_'"),
        (build_draft(name="v" * 65), "Voice name must be 1-64 letters, digits, '-' or '_'"),
        (build_draft(description="d" * 301), "Description must be at most 300 characters"),
        (
            build_draft(sample=FileUpload("notes.txt", io.BytesIO(b"x"))),
            "Unsupported audio type '.txt'. Use one of: .m4a, .mp3, .wav",
        ),
    ]
)
def invalid_voice_outcome(request, tmp_path, monkeypatch):
    draft, expected_message = request.param
    voices = build_voices(tmp_path, monkeypatch)
    error = capture(InvalidFilmRequestError, lambda: voices.service.create_voice(draft))
    return SimpleNamespace(actual=str(error), expected=expected_message)


@pytest.fixture
def duplicate_voice_error(tmp_path, monkeypatch):
    voices = build_voices(tmp_path, monkeypatch)
    return capture(
        FilmConflictError, lambda: voices.service.create_voice(build_draft(name="NARRATOR-EN"))
    )


@pytest.fixture
def oversized_voice(tmp_path, monkeypatch):
    voices = build_voices(tmp_path, monkeypatch)
    oversized = FileUpload("long.mp3", io.BytesIO(b"x" * (MAX_UPLOAD_MB * 1024 * 1024 + 1)))
    return create_failing(voices, build_draft(sample=oversized), FilmFileTooLargeError)


@pytest.fixture(params=[2_999, 180_001])
def out_of_range_voice(request, tmp_path, monkeypatch):
    voices = build_voices(tmp_path, monkeypatch, durations=[request.param])
    return create_failing(voices, build_draft(sample_text="Hi"), InvalidFilmRequestError)


@pytest.fixture(params=[3_000, 180_000])
def boundary_voice(request, tmp_path, monkeypatch):
    voices = build_voices(tmp_path, monkeypatch, durations=[request.param])
    return voices.service.create_voice(build_draft(sample_text="Hi"))


@pytest.fixture
def unreadable_voice(tmp_path, monkeypatch):
    voices = build_voices(tmp_path, monkeypatch, durations=CommandError("ffprobe failed"))
    return create_failing(voices, build_draft(sample_text="Hi"), InvalidFilmRequestError)


@pytest.fixture
def updated_voice(tmp_path, monkeypatch):
    voices = build_voices(tmp_path, monkeypatch)
    voices.service.update_voice(
        NARRATOR.id,
        VoiceChanges(name=" Narrator-EN ", sample_text=" New words ", description=""),
    )
    return voices.repository.update_voice.call_args.args


@pytest.fixture
def unchanged_voice(tmp_path, monkeypatch):
    voices = build_voices(tmp_path, monkeypatch)
    returned = voices.service.update_voice(NARRATOR.id, VoiceChanges())
    return SimpleNamespace(returned=returned, repository=voices.repository)


@pytest.fixture
def blank_sample_text_error(tmp_path, monkeypatch):
    voices = build_voices(tmp_path, monkeypatch)
    return capture(
        InvalidFilmRequestError,
        lambda: voices.service.update_voice(NARRATOR.id, VoiceChanges(sample_text="  ")),
    )


@pytest.fixture
def unknown_voice_error(tmp_path, monkeypatch):
    voices = build_voices(tmp_path, monkeypatch)
    return capture(VoiceNotFoundError, lambda: voices.service.delete_voice("vt-x"))


@pytest.fixture
def narrator_delete_error(tmp_path, monkeypatch):
    voices = build_voices(tmp_path, monkeypatch, narrator_count=1)
    return capture(FilmConflictError, lambda: voices.service.delete_voice(NARRATOR.id))


@pytest.fixture
def deleted_voice(tmp_path, monkeypatch):
    voices = build_voices(tmp_path, monkeypatch)
    sample_path = voices.files.voice_sample_path(NARRATOR.id, "wav")
    sample_path.parent.mkdir(parents=True)
    sample_path.write_bytes(b"RIFF")
    voices.service.delete_voice(NARRATOR.id)
    return SimpleNamespace(
        repository=voices.repository,
        is_folder_left=voices.files.voice_dir(NARRATOR.id).exists(),
    )


@pytest.fixture
def uploaded_consent(tmp_path, monkeypatch):
    voices = build_voices(tmp_path, monkeypatch)
    voices.service.upload_consent(NARRATOR.id, FileUpload("consent.wav", io.BytesIO(b"RIFF")))
    return SimpleNamespace(
        update_args=voices.repository.update_voice.call_args.args,
        stored_bytes=voices.files.voice_consent_path(NARRATOR.id, "wav").read_bytes(),
    )


@pytest.fixture
def unsupported_consent_error(tmp_path, monkeypatch):
    voices = build_voices(tmp_path, monkeypatch)
    return capture(
        InvalidFilmRequestError,
        lambda: voices.service.upload_consent(
            NARRATOR.id, FileUpload("notes.txt", io.BytesIO(b"x"))
        ),
    )


@pytest.fixture
def deleted_consent(tmp_path, monkeypatch):
    voices = build_voices(tmp_path, monkeypatch)
    consent_path = voices.files.voice_consent_path(NARRATOR.id, "wav")
    consent_path.parent.mkdir(parents=True)
    consent_path.write_bytes(b"RIFF")
    voices.service.delete_consent(NARRATOR.id)
    return SimpleNamespace(
        update_args=voices.repository.update_voice.call_args.args,
        is_consent_left=consent_path.exists(),
    )


def test_list_returns_the_voices_by_name(listed_voices):
    assert listed_voices == [NARRATOR]


def test_create_with_typed_text_stores_the_sample(typed_voice):
    assert typed_voice.voice.id == NEW_VOICE_ID
    assert typed_voice.voice.name == "narrator-auto"
    assert typed_voice.voice.description == "Calm"
    assert typed_voice.voice.sample_path == "voices/voice-new/sample.wav"
    assert typed_voice.voice.sample_text == "Typed words"
    assert typed_voice.voice.sample_duration_ms == SAMPLE_DURATION_MS
    assert typed_voice.voice.consent_path is None
    assert typed_voice.voice.provider_voices == {}
    assert typed_voice.stored_bytes == b"RIFF"


def test_create_with_typed_text_skips_whisper(typed_voice):
    assert typed_voice.transcriber.transcribe.called is False


def test_create_without_text_transcribes_the_sample(transcribed_voice):
    assert transcribed_voice.voice.sample_text == "Solar warning for the coast."
    assert transcribed_voice.voice.description is None


def test_transcription_uses_auto_language_on_a_temporary_wav(transcribed_voice):
    assert transcribed_voice.extract_source == "voices/voice-new/sample.wav"
    assert transcribed_voice.extract_target_name == "sample.wav"
    assert transcribed_voice.transcribe_language == "auto"
    assert transcribed_voice.is_work_folder_left is False


def test_create_fails_when_nothing_is_transcribed(untranscribed_outcome):
    assert untranscribed_outcome.message == (
        "Could not transcribe the sample. Type its text instead"
    )
    assert untranscribed_outcome.is_folder_left is False


def test_create_rejects_invalid_input(invalid_voice_outcome):
    assert invalid_voice_outcome.actual == invalid_voice_outcome.expected


def test_create_rejects_a_name_taken_in_another_case(duplicate_voice_error):
    assert str(duplicate_voice_error) == "A voice named 'NARRATOR-EN' already exists"


def test_create_rejects_a_sample_over_the_limit(oversized_voice):
    assert oversized_voice.message == "Audio exceeds 1 MB"
    assert oversized_voice.is_folder_left is False


def test_create_rejects_a_sample_outside_three_to_180_seconds(out_of_range_voice):
    assert out_of_range_voice.message == "Voice sample must be 3-180 seconds long"
    assert out_of_range_voice.is_folder_left is False


def test_create_accepts_the_duration_bounds(boundary_voice):
    assert boundary_voice.sample_text == "Hi"


def test_create_rejects_a_sample_ffprobe_cannot_read(unreadable_voice):
    assert unreadable_voice.message == "Could not read the voice sample"
    assert unreadable_voice.is_folder_left is False


def test_update_writes_every_sent_field(updated_voice):
    assert updated_voice == (
        "vt-1",
        {"sample_text": "New words", "description": None, "name": "Narrator-EN"},
    )


def test_update_without_changes_writes_nothing(unchanged_voice):
    assert unchanged_voice.returned is NARRATOR
    assert unchanged_voice.repository.update_voice.called is False


def test_update_rejects_blank_sample_text(blank_sample_text_error):
    assert str(blank_sample_text_error) == "Sample text must not be blank"


def test_unknown_voice_is_not_found(unknown_voice_error):
    assert str(unknown_voice_error) == "Voice vt-x not found"


def test_delete_refuses_the_narrator_of_a_project(narrator_delete_error):
    assert str(narrator_delete_error) == "Voice 'narrator-en' is the narrator of 1 project(s)"


def test_delete_removes_the_row_and_its_folder(deleted_voice):
    deleted_voice.repository.delete_voice.assert_called_once_with("vt-1")
    assert deleted_voice.is_folder_left is False


def test_consent_upload_stores_the_clip_and_drops_the_google_copy(uploaded_consent):
    assert uploaded_consent.update_args == (
        "vt-1",
        {"consent_path": "voices/vt-1/consent.wav", "provider_voices": {"elevenlabs": "el-1"}},
    )
    assert uploaded_consent.stored_bytes == b"RIFF"


def test_consent_upload_rejects_an_unsupported_type(unsupported_consent_error):
    assert str(unsupported_consent_error) == (
        "Unsupported audio type '.txt'. Use one of: .m4a, .mp3, .wav"
    )


def test_consent_delete_removes_the_clip_and_drops_the_google_copy(deleted_consent):
    assert deleted_consent.update_args == (
        "vt-1",
        {"consent_path": None, "provider_voices": {"elevenlabs": "el-1"}},
    )
    assert deleted_consent.is_consent_left is False
