import argparse
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel

ERROR_TEXT_LIMIT = 500
DEFAULT_HOST = "127.0.0.1"


@dataclass(frozen=True)
class SpeechOrder:
    text: str
    language: str
    sample_path: Path
    sample_text: str


class MusicOrder(BaseModel):
    prompt: str
    durationS: int | None = None
    instrumental: bool = True


@dataclass(frozen=True)
class Audio:
    content: bytes
    media_type: str


SpeechMaker = Callable[[SpeechOrder], Audio]
MusicMaker = Callable[[MusicOrder], Audio]
HealthCheck = Callable[[], None]


def create_app(
    title: str,
    make_speech: SpeechMaker | None = None,
    make_music: MusicMaker | None = None,
    check_health: HealthCheck | None = None,
) -> FastAPI:
    app = FastAPI(title=title)

    @app.exception_handler(Exception)
    def answer_error(_request: Request, error: Exception) -> PlainTextResponse:
        return PlainTextResponse(str(error)[:ERROR_TEXT_LIMIT] or type(error).__name__, 500)

    @app.get("/health")
    def health() -> dict[str, bool]:
        if check_health is not None:
            check_health()
        return {"ok": True}

    if make_speech is not None:

        @app.post("/speech")
        def speech(
            text: Annotated[str, Form()],
            sample: Annotated[UploadFile, File()],
            language: Annotated[str, Form()] = "",
            sampleText: Annotated[str, Form()] = "",
        ) -> Response:
            suffix = Path(sample.filename or "sample.wav").suffix
            with tempfile.TemporaryDirectory() as work_dir:
                sample_path = Path(work_dir) / f"sample{suffix}"
                sample_path.write_bytes(sample.file.read())
                audio = make_speech(SpeechOrder(text, language, sample_path, sampleText))
            return Response(audio.content, media_type=audio.media_type)

    if make_music is not None:

        @app.post("/music")
        def music(order: MusicOrder) -> Response:
            audio = make_music(order)
            return Response(audio.content, media_type=audio.media_type)

    return app


def serve(app: FastAPI, default_port: int) -> None:
    parser = argparse.ArgumentParser(description=app.title)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=default_port)
    arguments = parser.parse_args()
    uvicorn.run(app, host=arguments.host, port=arguments.port)
