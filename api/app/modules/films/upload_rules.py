from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from app.modules.films.errors import InvalidFilmRequestError


@dataclass(frozen=True)
class FileUpload:
    filename: str
    stream: BinaryIO


@dataclass(frozen=True)
class UploadKind:
    extensions: frozenset[str]
    unsupported_message: str
    too_large_message: str


IMAGE_UPLOAD = UploadKind(
    extensions=frozenset({".jpeg", ".jpg", ".png", ".webp"}),
    unsupported_message="Unsupported image type '{extension}'. Use one of: {supported}",
    too_large_message="Image exceeds {max_mb} MB",
)
AUDIO_UPLOAD = UploadKind(
    extensions=frozenset({".wav", ".mp3", ".m4a"}),
    unsupported_message="Unsupported audio type '{extension}'. Use one of: {supported}",
    too_large_message="Audio exceeds {max_mb} MB",
)


def to_upload_extension(filename: str, kind: UploadKind) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in kind.extensions:
        supported = ", ".join(sorted(kind.extensions))
        raise InvalidFilmRequestError(
            kind.unsupported_message.format(extension=extension, supported=supported)
        )
    return extension.removeprefix(".")


def build_too_large_message(kind: UploadKind, max_mb: int) -> str:
    return kind.too_large_message.format(max_mb=max_mb)
