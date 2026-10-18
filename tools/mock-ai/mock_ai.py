#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import re
import select
import socket
import ssl
import stat
import subprocess
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import certifi
from ai_answers import build_scenario_answer
from mock_state import (
    CALLS_FILE_NAME,
    SCENARIO_FILE_NAME,
    SCENARIO_USES_FILE_NAME,
    AskView,
    SentImage,
    decode_base64_image,
    describe_ask,
    find_state_dir,
    lock_state,
    record_call,
    split_into_chunks,
    take_scenario_rule,
)

LOOPBACK_HOST = "127.0.0.1"
DEFAULT_PROXY_PORT = 5077
GEMINI_HOST = "generativelanguage.googleapis.com"
OPENAI_HOST = "api.openai.com"
MOCKED_HOSTS = frozenset({GEMINI_HOST, OPENAI_HOST})
GEMINI_STREAM_PATH = re.compile(r"^/v1beta/models/([^/:?]+):streamGenerateContent(\?.*)?$")
OPENAI_RESPONSES_PATH = "/v1/responses"
GEMINI_KEY_HEADER = "x-goog-api-key"
BEARER_PREFIX = "Bearer "
DATA_URL_PREFIX = "data:image/jpeg;base64,"
TUNNEL_BUFFER_BYTES = 65536
TUNNEL_CONNECT_TIMEOUT_SEC = 30
DEFAULT_CHUNK_COUNT = 3
TOOLS_DIR = Path(__file__).resolve().parent
CLAUDE_MOCK = TOOLS_DIR / "mock_claude.py"
WHISPER_MOCK = TOOLS_DIR / "mock_whisper.py"
WHISPER_MODEL_NAME = "ggml-mock.bin"
ENV_FILE_NAME = "mock-ai.env"

logger = logging.getLogger("mock-ai")


def gemini_body_to_ask(model: str, body: dict[str, Any]) -> AskView:
    instructions = "".join(
        part.get("text", "") for part in body.get("systemInstruction", {}).get("parts", [])
    )
    parts = (body.get("contents") or [{}])[0].get("parts", [])
    texts: list[str] = []
    images: list[SentImage] = []
    for part in parts:
        if "text" in part:
            texts.append(part["text"])
        elif "inlineData" in part:
            label = texts.pop() if len(texts) > 1 else ""
            images.append(decode_base64_image(label, part["inlineData"]["data"]))
    schema = body.get("generationConfig", {}).get("responseJsonSchema")
    return AskView("gemini", model, instructions, texts[0] if texts else "", images, schema)


def openai_body_to_ask(body: dict[str, Any]) -> AskView:
    content = (body.get("input") or [{}])[0].get("content", [])
    texts: list[str] = []
    images: list[SentImage] = []
    for block in content:
        if block.get("type") == "input_text":
            texts.append(block["text"])
        elif block.get("type") == "input_image":
            label = texts.pop() if len(texts) > 1 else ""
            image_url = str(block.get("image_url", ""))
            images.append(decode_base64_image(label, image_url.split(",", 1)[-1]))
    schema = body.get("text", {}).get("format", {}).get("schema")
    return AskView(
        "openai",
        str(body.get("model", "")),
        str(body.get("instructions", "")),
        texts[0] if texts else "",
        images,
        schema,
    )


def build_gemini_events(answer: str, rule: dict[str, Any]) -> list[dict[str, Any]]:
    if rule.get("block"):
        return [{"promptFeedback": {"blockReason": rule["block"]}}]
    chunks = rule.get("chunks") or split_into_chunks(answer, DEFAULT_CHUNK_COUNT)
    events = [
        {"candidates": [{"content": {"role": "model", "parts": [{"text": chunk}]}, "index": 0}]}
        for chunk in chunks
    ]
    events[-1]["candidates"][0]["finishReason"] = rule.get("finish_reason", "STOP")
    events[-1]["usageMetadata"] = {"promptTokenCount": 1, "candidatesTokenCount": len(chunks)}
    return events


def build_openai_events(model: str, answer: str, rule: dict[str, Any]) -> list[dict[str, Any]]:
    response = {"id": f"resp_mock_{uuid.uuid4().hex[:12]}", "object": "response", "model": model}
    events: list[dict[str, Any]] = [
        {"type": "response.created", "response": {**response, "status": "in_progress"}},
        {"type": "response.in_progress", "response": {**response, "status": "in_progress"}},
    ]
    if rule.get("fail"):
        error = {"code": "server_error", "message": rule["fail"]}
        return [
            *events,
            {
                "type": "response.failed",
                "response": {**response, "status": "failed", "error": error},
            },
        ]
    if rule.get("incomplete"):
        details = {"reason": rule["incomplete"]}
        incomplete = {**response, "status": "incomplete", "incomplete_details": details}
        return [*events, {"type": "response.incomplete", "response": incomplete}]
    if rule.get("refusal"):
        refusal = {"type": "response.refusal.delta", "delta": rule["refusal"], "output_index": 0}
        return [
            *events,
            refusal,
            {"type": "response.completed", "response": {**response, "status": "completed"}},
        ]
    chunks = rule.get("chunks") or split_into_chunks(answer, DEFAULT_CHUNK_COUNT)
    deltas = [
        {
            "type": "response.output_text.delta",
            "delta": chunk,
            "output_index": 0,
            "content_index": 0,
        }
        for chunk in chunks
    ]
    done = {
        "type": "response.output_text.done",
        "text": answer,
        "output_index": 0,
        "content_index": 0,
    }
    completed = {"type": "response.completed", "response": {**response, "status": "completed"}}
    return [*events, *deltas, done, completed]


def to_key_facts(api_key: str | None, path: str) -> dict[str, Any]:
    return {
        "hasApiKey": bool(api_key),
        "apiKeyLast4": api_key[-4:] if api_key else None,
        "isKeyInUrl": bool(api_key) and api_key in path,
    }


class AiApiHandler(BaseHTTPRequestHandler):
    server_version = "MockAi/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        headers = getattr(self, "headers", None)
        logger.info("%s %s", headers.get("Host", "-") if headers else "-", format % args)

    def do_POST(self) -> None:
        body_bytes = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        body = json.loads(body_bytes or b"{}")
        gemini_path = GEMINI_STREAM_PATH.match(self.path)
        if gemini_path:
            self._answer_gemini(gemini_path.group(1), body, len(body_bytes))
        elif self.path.split("?", 1)[0] == OPENAI_RESPONSES_PATH:
            self._answer_openai(body, len(body_bytes))
        else:
            self._send_json(404, {"error": {"message": f"mock-ai does not serve {self.path}"}})

    def _answer_gemini(self, model: str, body: dict[str, Any], body_bytes: int) -> None:
        state_dir = self.server.state_dir
        ask = gemini_body_to_ask(model, body)
        rule = take_scenario_rule(state_dir, ask.ai, f"{ask.instructions}\n{ask.message}") or {}
        generation_config = dict(body.get("generationConfig", {}))
        generation_config.pop("responseJsonSchema", None)
        record_call(
            state_dir,
            {
                **describe_ask(ask),
                "url": f"https://{self.headers.get('Host')}{self.path}",
                **to_key_facts(self.headers.get(GEMINI_KEY_HEADER), self.path),
                "bodyKeys": sorted(body),
                "generationConfig": generation_config,
                "bodyBytes": body_bytes,
                "scenario": rule or None,
            },
        )
        if self._send_scenario_failure(rule):
            return
        answer = build_scenario_answer(ask, rule)
        self._stream_sse(build_gemini_events(answer, rule), rule, with_event_names=False)

    def _answer_openai(self, body: dict[str, Any], body_bytes: int) -> None:
        state_dir = self.server.state_dir
        ask = openai_body_to_ask(body)
        rule = take_scenario_rule(state_dir, ask.ai, f"{ask.instructions}\n{ask.message}") or {}
        authorization = self.headers.get("Authorization", "")
        api_key = (
            authorization[len(BEARER_PREFIX) :] if authorization.startswith(BEARER_PREFIX) else None
        )
        text_format = dict(body.get("text", {}).get("format", {}))
        text_format.pop("schema", None)
        record_call(
            state_dir,
            {
                **describe_ask(ask),
                "url": f"https://{self.headers.get('Host')}{self.path}",
                **to_key_facts(api_key, self.path),
                "bodyKeys": sorted(body),
                "stream": body.get("stream"),
                "store": body.get("store"),
                "textFormat": text_format or None,
                "bodyBytes": body_bytes,
                "scenario": rule or None,
            },
        )
        if self._send_scenario_failure(rule):
            return
        answer = build_scenario_answer(ask, rule)
        self._stream_sse(build_openai_events(ask.model, answer, rule), rule, with_event_names=True)

    def _send_scenario_failure(self, rule: dict[str, Any]) -> bool:
        time.sleep(float(rule.get("silent_sec", 0)))
        if not rule.get("status"):
            return False
        message = rule.get("error", "mock error")
        self._send_json(
            int(rule["status"]), {"error": {"code": rule["status"], "message": message}}
        )
        return True

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _stream_sse(
        self, events: list[dict[str, Any]], rule: dict[str, Any], with_event_names: bool
    ) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        for index, event in enumerate(events):
            if index:
                time.sleep(float(rule.get("chunk_every_sec", 0)))
            event_line = f"event: {event['type']}\n" if with_event_names else ""
            self.wfile.write(
                f"{event_line}data: {json.dumps(event, ensure_ascii=False)}\r\n\r\n".encode()
            )
            self.wfile.flush()


class ProxyHandler(BaseHTTPRequestHandler):
    server_version = "MockAiProxy/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug(format, *args)

    def do_CONNECT(self) -> None:
        host, _, port = self.path.partition(":")
        if host in MOCKED_HOSTS:
            self._serve_mocked_host(host)
        else:
            self._tunnel(host, int(port or 443))
        self.close_connection = True

    def _serve_mocked_host(self, host: str) -> None:
        self.send_response(200, "Connection Established")
        self.end_headers()
        self.wfile.flush()
        try:
            tls_socket = self.server.tls_context.wrap_socket(self.connection, server_side=True)
        except (ssl.SSLError, ConnectionError) as error:
            logger.warning("TLS with the API failed for %s: %s", host, error)
            return
        try:
            AiApiHandler(tls_socket, self.client_address, self.server)
        except (ssl.SSLError, ConnectionError) as error:
            logger.warning("Answer to %s broke off: %s", host, error)
        finally:
            tls_socket.close()

    def _tunnel(self, host: str, port: int) -> None:
        try:
            upstream = socket.create_connection((host, port), timeout=TUNNEL_CONNECT_TIMEOUT_SEC)
        except OSError as error:
            self.send_error(502, f"Cannot reach {host}:{port}: {error}")
            return
        self.send_response(200, "Connection Established")
        self.end_headers()
        self.wfile.flush()
        pipe_sockets(self.connection, upstream)


def pipe_sockets(client: socket.socket, upstream: socket.socket) -> None:
    sockets = [client, upstream]
    try:
        while True:
            readable, _, broken = select.select(sockets, [], sockets)
            if broken:
                return
            for source in readable:
                data = source.recv(TUNNEL_BUFFER_BYTES)
                if not data:
                    return
                (upstream if source is client else client).sendall(data)
    except OSError:
        return
    finally:
        upstream.close()


class MockAiServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port: int, state_dir: Path, tls_context: ssl.SSLContext):
        super().__init__((LOOPBACK_HOST, port), ProxyHandler)
        self.state_dir = state_dir
        self.tls_context = tls_context


def ensure_certificate(state_dir: Path) -> tuple[Path, Path, Path]:
    certificate = state_dir / "mock-ai-cert.pem"
    key = state_dir / "mock-ai-key.pem"
    bundle = state_dir / "ca-bundle.pem"
    if not certificate.exists() or not key.exists():
        subject_names = ",".join(f"DNS:{host}" for host in sorted(MOCKED_HOSTS))
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
                f"/CN={GEMINI_HOST}",
                "-addext",
                f"subjectAltName={subject_names}",
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


def prepare_fakes(state_dir: Path) -> Path:
    for script in (CLAUDE_MOCK, WHISPER_MOCK):
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    whisper_model = state_dir / WHISPER_MODEL_NAME
    whisper_model.write_bytes(b"mock whisper model")
    return whisper_model


def build_api_env(port: int, state_dir: Path, bundle: Path, whisper_model: Path) -> dict[str, str]:
    return {
        "HTTPS_PROXY": f"http://{LOOPBACK_HOST}:{port}",
        "NO_PROXY": "localhost,127.0.0.1",
        "SSL_CERT_FILE": str(bundle),
        "CLAUDE_BIN": str(CLAUDE_MOCK),
        "WHISPER_BIN": str(WHISPER_MOCK),
        "WHISPER_MODEL_PATH": str(whisper_model),
        "MOCK_AI_STATE_DIR": str(state_dir),
    }


def clear_state(state_dir: Path) -> None:
    with lock_state(state_dir):
        for name in (CALLS_FILE_NAME, SCENARIO_FILE_NAME, SCENARIO_USES_FILE_NAME):
            (state_dir / name).unlink(missing_ok=True)


def set_scenario(state_dir: Path, rules: list[dict[str, Any]]) -> None:
    with lock_state(state_dir):
        (state_dir / SCENARIO_FILE_NAME).write_text(json.dumps(rules, ensure_ascii=False))
        (state_dir / SCENARIO_USES_FILE_NAME).unlink(missing_ok=True)


def serve(port: int, state_dir: Path) -> None:
    clear_state(state_dir)
    certificate, key, bundle = ensure_certificate(state_dir)
    whisper_model = prepare_fakes(state_dir)
    api_env = build_api_env(port, state_dir, bundle, whisper_model)
    env_file = state_dir / ENV_FILE_NAME
    env_file.write_text("".join(f"{name}={value}\n" for name, value in api_env.items()))
    tls_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls_context.load_cert_chain(certificate, key)
    server = MockAiServer(port, state_dir, tls_context)
    logger.info(
        "Proxy on http://%s:%d — mocks %s, tunnels every other host",
        LOOPBACK_HOST,
        port,
        ", ".join(sorted(MOCKED_HOSTS)),
    )
    logger.info("Calls: %s", state_dir / CALLS_FILE_NAME)
    logger.info("Start the API with the variables in %s", env_file)
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock AI models for the video-tool test stack")
    parser.add_argument("--state-dir", type=Path)
    commands = parser.add_subparsers(dest="command")
    serve_parser = commands.add_parser("serve", help="run the Gemini / OpenAI proxy (default)")
    serve_parser.add_argument("--port", type=int, default=DEFAULT_PROXY_PORT)
    scenario_parser = commands.add_parser("scenario", help="replace the scenario rules")
    scenario_parser.add_argument("rules", help="JSON list of rules; [] clears them")
    commands.add_parser("clear", help="clear the calls log and the scenario")
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    state_dir = arguments.state_dir or find_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)
    if arguments.command == "scenario":
        set_scenario(state_dir, json.loads(arguments.rules))
    elif arguments.command == "clear":
        clear_state(state_dir)
    else:
        serve(getattr(arguments, "port", DEFAULT_PROXY_PORT), state_dir)


if __name__ == "__main__":
    main()
