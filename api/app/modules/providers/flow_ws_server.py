import contextlib
import json
import logging
import re
import threading
from dataclasses import dataclass
from typing import Any

from websockets.exceptions import ConnectionClosed
from websockets.sync.server import Server, ServerConnection, serve

from app.modules.providers.errors import ExtensionNotConnectedError
from app.modules.providers.flow_extension import (
    REQUEST_ID_KEY,
    CommandSender,
    FlowExtensionBridge,
)

LOOPBACK_HOST = "127.0.0.1"
EXTENSION_ORIGIN_PATTERN = re.compile(r"chrome-extension://[a-p]{32}")
MAX_MESSAGE_BYTES = 64 * 1024 * 1024
STOP_TIMEOUT_SEC = 10.0
THREAD_NAME = "flow-ws-server"
TYPE_KEY = "type"
PING_TYPE = "ping"
READY_TYPE = "extension_ready"
VERSION_KEY = "extensionVersion"
PONG_MESSAGE = json.dumps({TYPE_KEY: "pong"})

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _RunningServer:
    server: Server
    thread: threading.Thread


class FlowWsServer:
    def __init__(self, bridge: FlowExtensionBridge, port: int):
        self._bridge = bridge
        self._port = port
        self._running: _RunningServer | None = None

    def start(self) -> None:
        try:
            server = serve(
                self._handle_connection,
                LOOPBACK_HOST,
                self._port,
                origins=[EXTENSION_ORIGIN_PATTERN],
                max_size=MAX_MESSAGE_BYTES,
            )
        except OSError:
            logger.exception("Flow extension server could not listen on port %d", self._port)
            return
        thread = threading.Thread(target=server.serve_forever, name=THREAD_NAME, daemon=True)
        thread.start()
        self._running = _RunningServer(server, thread)
        logger.info("Flow extension server listening on ws://%s:%d", LOOPBACK_HOST, self._port)

    def stop(self) -> None:
        if self._running is None:
            return
        self._running.server.shutdown()
        self._running.thread.join(STOP_TIMEOUT_SEC)
        self._running = None
        logger.info("Flow extension server stopped")

    def _handle_connection(self, connection: ServerConnection) -> None:
        send_command = _build_command_sender(connection)
        self._bridge.register_connection(send_command)
        logger.info("Flow extension connected")
        try:
            with contextlib.suppress(ConnectionClosed):
                for raw_message in connection:
                    self._handle_message(connection, _to_message(raw_message))
        finally:
            self._bridge.unregister_connection(send_command)
            logger.info("Flow extension disconnected")

    def _handle_message(self, connection: ServerConnection, message: dict[str, Any]) -> None:
        message_type = message.get(TYPE_KEY)
        if message_type == PING_TYPE:
            connection.send(PONG_MESSAGE)
        elif message_type == READY_TYPE:
            logger.info("Flow extension ready, version %s", message.get(VERSION_KEY))
        elif message_type is None and REQUEST_ID_KEY in message:
            self._bridge.receive_reply(message)


def _build_command_sender(connection: ServerConnection) -> CommandSender:
    def send_command(command: dict[str, Any]) -> None:
        try:
            connection.send(json.dumps(command))
        except ConnectionClosed as error:
            raise ExtensionNotConnectedError() from error

    return send_command


def _to_message(raw_message: str | bytes) -> dict[str, Any]:
    try:
        message = json.loads(raw_message)
    except ValueError:
        logger.warning("Flow extension sent a message that is not JSON")
        return {}
    return message if isinstance(message, dict) else {}
