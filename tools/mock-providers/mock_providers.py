import argparse
import base64
import json
import logging
import math
import re
import ssl
import struct
import subprocess
import tempfile
import threading
import time
import uuid
import wave
import zlib
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import certifi
from websockets.exceptions import ConnectionClosed, InvalidHandshake
from websockets.sync.client import connect

LOOPBACK_HOST = "127.0.0.1"
DEFAULT_LOCAL_PORT = 5078
DEFAULT_CONTENT_PORT = 5079
DEFAULT_FLOW_WS_PORT = 5074
DEFAULT_STATE_DIR = Path(tempfile.gettempdir()) / "video-tool-mock-providers"
EXTENSION_ORIGIN = "chrome-extension://" + "a" * 32
EXTENSION_VERSION = "mock"
RECONNECT_EVERY_SEC = 2.0
MAX_MESSAGE_BYTES = 64 * 1024 * 1024

ANSWER_SENTINEL = ")]}'"
ENVELOPE_TAG = "wrb.fr"
OPERATION_DONE_STATUS = "CAE"
RPC_CREATE_PROJECT = "jHPbke"
RPC_UPLOAD_IMAGE = "maseQ"
RPC_GENERATE_IMAGE = "ogiZ0b"
RPC_GENERATE_VIDEO = "eb1hJf"
RPC_OPERATION = "jwpduf"
RPC_PROJECT_MEDIA = "Zzl0ze"
RPC_MEDIA = "as29s"
UNKNOWN_RPC_ERROR = [3]
IMAGE_ASPECT_PORTRAIT = 2
VIDEO_ASPECT_PORTRAIT = 1
CONTENT_HOST_PATH = "flow-content.google"

LANDSCAPE_IMAGE_SIZE = (1376, 768)
PORTRAIT_IMAGE_SIZE = (768, 1376)
LANDSCAPE_VIDEO_SIZE = (1280, 720)
PORTRAIT_VIDEO_SIZE = (720, 1280)
DEFAULT_CLIP_LENGTH_S = 8
CLIP_LENGTH_PATTERN = re.compile(r"_(\d+)s$")
VIDEO_FPS = 24
COLORS = ((200, 60, 60), (60, 160, 90), (70, 90, 200), (210, 170, 40), (150, 70, 180))

AUDIO_SAMPLE_RATE = 24000
SPEECH_SECONDS_PER_CHARACTER = 0.06
MIN_SPEECH_S = 1.0
MAX_SPEECH_S = 7.0
SPEECH_FREQUENCY_HZ = 440
MUSIC_FREQUENCY_HZ = 220
DEFAULT_MUSIC_S = 30
MAX_MUSIC_S = 600
AUDIO_AMPLITUDE = 0.3
COMPACT_JSON = (",", ":")
SPEECH_TEXT_PATTERN = re.compile(rb'name="text"\r\n\r\n(.*?)\r\n--', re.S)

logger = logging.getLogger("mock-providers")


@dataclass(frozen=True)
class VideoOrder:
    media_id: str
    is_portrait: bool
    length_s: int


class CallLog:
    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()

    def record(self, entry: dict[str, Any]) -> None:
        line = json.dumps({"at": time.strftime("%H:%M:%S"), **entry}, ensure_ascii=False)
        with self._lock, self._path.open("a", encoding="utf-8") as log_file:
            log_file.write(line + "\n")
        logger.info("%s", line)


class MediaFactory:
    def __init__(self, state_dir: Path, ffmpeg_bin: str):
        self._state_dir = state_dir
        self._ffmpeg_bin = ffmpeg_bin
        self._lock = threading.Lock()
        self._image_count = 0

    def build_image(self, width: int, height: int) -> bytes:
        with self._lock:
            self._image_count += 1
            color = COLORS[self._image_count % len(COLORS)]
        return build_png(width, height, color)

    def find_video(self, is_portrait: bool, length_s: int) -> Path:
        width, height = PORTRAIT_VIDEO_SIZE if is_portrait else LANDSCAPE_VIDEO_SIZE
        path = self._state_dir / f"clip-{width}x{height}-{length_s}s.mp4"
        with self._lock:
            if not path.exists():
                self._render_video(path, width, height, length_s)
        return path

    def _render_video(self, path: Path, width: int, height: int, length_s: int) -> None:
        subprocess.run(
            [
                self._ffmpeg_bin,
                "-y",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"testsrc2=size={width}x{height}:rate={VIDEO_FPS}",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=330:sample_rate=48000",
                "-t",
                str(length_s),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                str(path),
            ],
            check=True,
        )


class FlowRpcAnswers:
    def __init__(self, content_base_url: str, calls: CallLog):
        self._content_base_url = content_base_url
        self._calls = calls
        self._lock = threading.Lock()
        self._orders_by_operation: dict[str, VideoOrder] = {}
        self._orders_by_media: dict[str, VideoOrder] = {}

    def answer(self, params: dict[str, Any]) -> str:
        rpc_id = str(params.get("rpcid"))
        inner = json.loads(json.loads(params["freq"])[0][0][1])
        payload = self._build_payload(rpc_id, inner, params)
        if payload is None:
            return to_answer_text([ENVELOPE_TAG, rpc_id, None, None, None, UNKNOWN_RPC_ERROR])
        payload_text = json.dumps(payload, separators=COMPACT_JSON)
        return to_answer_text([ENVELOPE_TAG, rpc_id, payload_text, None, None, None, "generic"])

    def _build_payload(self, rpc_id: str, inner: Any, params: dict[str, Any]) -> Any:
        if rpc_id == RPC_CREATE_PROJECT:
            project_id = new_id()
            self._calls.record(
                {"flow": "create_project", "title": inner[1][1][0], "projectId": project_id}
            )
            return [project_id]
        if rpc_id == RPC_UPLOAD_IMAGE:
            media_id = new_id()
            self._calls.record({"flow": "upload", "fileName": inner[8], "mediaId": media_id})
            return [[media_id]]
        if rpc_id == RPC_GENERATE_IMAGE:
            return self._generate_image(inner[1][0])
        if rpc_id == RPC_GENERATE_VIDEO:
            return self._generate_video(inner[0][0])
        if rpc_id == RPC_OPERATION:
            return to_operation_payload(inner[2][0][0])
        if rpc_id == RPC_PROJECT_MEDIA:
            return self._list_media(str(params.get("match", "")))
        if rpc_id == RPC_MEDIA:
            return self._find_video_url(inner[0])
        return None

    def _generate_image(self, item: list[Any]) -> Any:
        is_portrait = item[4] == IMAGE_ASPECT_PORTRAIT
        image_path = f"{CONTENT_HOST_PATH}/image/{new_id()}.png?portrait={int(is_portrait)}"
        image_url = f"{self._content_base_url}/{image_path}"
        self._calls.record(
            {
                "flow": "image",
                "model": item[5],
                "prompt": item[8][0][0][0],
                "inputs": len(item[2] or []),
                "portrait": is_portrait,
            }
        )
        return [[[image_url]]]

    def _generate_video(self, request: list[Any]) -> Any:
        model_id = str(request[1])
        length_match = CLIP_LENGTH_PATTERN.search(model_id)
        order = VideoOrder(
            media_id=new_id(),
            is_portrait=request[2] == VIDEO_ASPECT_PORTRAIT,
            length_s=int(length_match.group(1)) if length_match else DEFAULT_CLIP_LENGTH_S,
        )
        operation_id = new_id()
        with self._lock:
            self._orders_by_operation[operation_id] = order
            self._orders_by_media[order.media_id] = order
        self._calls.record(
            {
                "flow": "video",
                "model": model_id,
                "prompt": request[0][2][0][0][0],
                "portrait": order.is_portrait,
                "lengthS": order.length_s,
                "operationId": operation_id,
            }
        )
        return to_operation_payload(operation_id)

    def _list_media(self, operation_id: str) -> Any:
        with self._lock:
            order = self._orders_by_operation.get(operation_id)
        if order is None:
            return [[]]
        return [[operation_id, None, None, order.media_id]]

    def _find_video_url(self, media_id: str) -> Any:
        with self._lock:
            order = self._orders_by_media.get(media_id)
        if order is None:
            return None
        query = f"portrait={int(order.is_portrait)}&length={order.length_s}"
        return [[f"{self._content_base_url}/{CONTENT_HOST_PATH}/video/{media_id}.mp4?{query}"]]


class MockFlowExtension:
    def __init__(self, ws_url: str, answers: FlowRpcAnswers):
        self._ws_url = ws_url
        self._answers = answers

    def run_forever(self) -> None:
        while True:
            try:
                self._serve_one_connection()
            except (OSError, InvalidHandshake, ConnectionClosed) as error:
                logger.info("Flow extension not connected (%s); retrying", type(error).__name__)
            time.sleep(RECONNECT_EVERY_SEC)

    def _serve_one_connection(self) -> None:
        with connect(
            self._ws_url, origin=EXTENSION_ORIGIN, max_size=MAX_MESSAGE_BYTES
        ) as connection:
            connection.send(
                json.dumps({"type": "extension_ready", "extensionVersion": EXTENSION_VERSION})
            )
            logger.info("Flow extension connected to %s", self._ws_url)
            for raw_message in connection:
                reply = self._reply_to(json.loads(raw_message))
                if reply is not None:
                    connection.send(json.dumps(reply))

    def _reply_to(self, message: dict[str, Any]) -> dict[str, Any] | None:
        if "id" not in message or message.get("method") != "batch_rpc":
            return None
        try:
            return {"id": message["id"], "data": self._answers.answer(message.get("params") or {})}
        except (KeyError, IndexError, TypeError, ValueError) as error:
            return {"id": message["id"], "error": f"mock could not read the request: {error!r}"}


def build_local_handler(media: MediaFactory, calls: CallLog) -> type[BaseHTTPRequestHandler]:
    class LocalHandler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            if self.path == "/health":
                send_body(self, b'{"ok":true}', "application/json")
            elif self.path == "/sdapi/v1/sd-models":
                send_body(self, b"[]", "application/json")
            else:
                send_body(self, b"not found", "text/plain", 404)

        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if self.path in ("/sdapi/v1/txt2img", "/sdapi/v1/img2img"):
                self._answer_sd(json.loads(body))
            elif self.path == "/speech":
                self._answer_speech(body)
            elif self.path == "/music":
                self._answer_music(json.loads(body))
            else:
                send_body(self, b"not found", "text/plain", 404)

        def _answer_sd(self, request: dict[str, Any]) -> None:
            image = media.build_image(int(request["width"]), int(request["height"]))
            calls.record(
                {
                    "local": self.path,
                    "prompt": request.get("prompt"),
                    "width": request["width"],
                    "height": request["height"],
                    "initImages": len(request.get("init_images") or []),
                }
            )
            answer = {"images": [base64.b64encode(image).decode("ascii")]}
            send_body(self, json.dumps(answer).encode(), "application/json")

        def _answer_speech(self, body: bytes) -> None:
            match = SPEECH_TEXT_PATTERN.search(body)
            text = match.group(1).decode("utf-8", "replace") if match else ""
            duration_s = min(
                max(len(text) * SPEECH_SECONDS_PER_CHARACTER, MIN_SPEECH_S), MAX_SPEECH_S
            )
            calls.record({"local": "/speech", "text": text, "durationS": round(duration_s, 2)})
            send_body(self, build_wav(duration_s, SPEECH_FREQUENCY_HZ), "audio/wav")

        def _answer_music(self, request: dict[str, Any]) -> None:
            duration_s = min(float(request.get("durationS") or DEFAULT_MUSIC_S), MAX_MUSIC_S)
            calls.record({"local": "/music", **request})
            send_body(self, build_wav(duration_s, MUSIC_FREQUENCY_HZ), "audio/wav")

    return LocalHandler


def build_content_handler(media: MediaFactory) -> type[BaseHTTPRequestHandler]:
    class ContentHandler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            url = urlparse(self.path)
            query = parse_qs(url.query)
            is_portrait = query.get("portrait") == ["1"]
            if url.path.startswith(f"/{CONTENT_HOST_PATH}/image/"):
                width, height = PORTRAIT_IMAGE_SIZE if is_portrait else LANDSCAPE_IMAGE_SIZE
                send_body(self, media.build_image(width, height), "image/png")
            elif url.path.startswith(f"/{CONTENT_HOST_PATH}/video/"):
                length_s = int(query.get("length", [DEFAULT_CLIP_LENGTH_S])[0])
                send_body(self, media.find_video(is_portrait, length_s).read_bytes(), "video/mp4")
            else:
                send_body(self, b"not found", "text/plain", 404)

    return ContentHandler


def send_body(
    handler: BaseHTTPRequestHandler, body: bytes, content_type: str, status: int = 200
) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def build_png(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    row = b"\x00" + bytes(color) * width
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + to_png_chunk(b"IHDR", header)
        + to_png_chunk(b"IDAT", zlib.compress(row * height, 6))
        + to_png_chunk(b"IEND", b"")
    )


def to_png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


def build_wav(duration_s: float, frequency_hz: int) -> bytes:
    peak = int(AUDIO_AMPLITUDE * 32767)
    one_second = b"".join(
        struct.pack(
            "<h", int(peak * math.sin(2 * math.pi * frequency_hz * index / AUDIO_SAMPLE_RATE))
        )
        for index in range(AUDIO_SAMPLE_RATE)
    )
    sample_bytes = int(duration_s * AUDIO_SAMPLE_RATE) * 2
    samples = (one_second * (sample_bytes // len(one_second) + 1))[:sample_bytes]
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(AUDIO_SAMPLE_RATE)
        wav_file.writeframes(samples)
    return buffer.getvalue()


def to_answer_text(envelope: list[Any]) -> str:
    return f"{ANSWER_SENTINEL}\n{json.dumps([envelope], separators=COMPACT_JSON)}"


def to_operation_payload(operation_id: str) -> Any:
    return [None, None, [[operation_id, None, None, OPERATION_DONE_STATUS]]]


def new_id() -> str:
    return str(uuid.uuid4())


def ensure_certificate(state_dir: Path) -> tuple[Path, Path, Path]:
    certificate = state_dir / "mock-cert.pem"
    key = state_dir / "mock-key.pem"
    bundle = state_dir / "ca-bundle.pem"
    if not certificate.exists() or not key.exists():
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "30",
                "-subj",
                f"/CN={LOOPBACK_HOST}",
                "-addext",
                f"subjectAltName=IP:{LOOPBACK_HOST},DNS:localhost",
                "-keyout",
                str(key),
                "-out",
                str(certificate),
            ],
            check=True,
            capture_output=True,
        )
    bundle.write_text(Path(certifi.where()).read_text() + "\n" + certificate.read_text())
    return certificate, key, bundle


def start_server(server: ThreadingHTTPServer, name: str) -> None:
    threading.Thread(target=server.serve_forever, name=name, daemon=True).start()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mock media providers for the video-tool test stack"
    )
    parser.add_argument("--local-port", type=int, default=DEFAULT_LOCAL_PORT)
    parser.add_argument("--content-port", type=int, default=DEFAULT_CONTENT_PORT)
    parser.add_argument("--flow-ws-port", type=int, default=DEFAULT_FLOW_WS_PORT)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    parser.add_argument("--no-flow-extension", action="store_true")
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

    arguments.state_dir.mkdir(parents=True, exist_ok=True)
    calls = CallLog(arguments.state_dir / "calls.jsonl")
    media = MediaFactory(arguments.state_dir, arguments.ffmpeg_bin)
    certificate, key, bundle = ensure_certificate(arguments.state_dir)

    local_server = ThreadingHTTPServer(
        (LOOPBACK_HOST, arguments.local_port), build_local_handler(media, calls)
    )
    content_server = ThreadingHTTPServer(
        (LOOPBACK_HOST, arguments.content_port), build_content_handler(media)
    )
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls_context.load_cert_chain(certificate, key)
    content_server.socket = tls_context.wrap_socket(content_server.socket, server_side=True)
    start_server(local_server, "mock-local")
    start_server(content_server, "mock-flow-content")
    logger.info("Local providers on http://%s:%d", LOOPBACK_HOST, arguments.local_port)
    logger.info("Flow content on https://%s:%d", LOOPBACK_HOST, arguments.content_port)
    logger.info("Start the API with SSL_CERT_FILE=%s", bundle)

    if arguments.no_flow_extension:
        threading.Event().wait()
    answers = FlowRpcAnswers(f"https://{LOOPBACK_HOST}:{arguments.content_port}", calls)
    MockFlowExtension(f"ws://{LOOPBACK_HOST}:{arguments.flow_ws_port}", answers).run_forever()


if __name__ == "__main__":
    main()
