import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from websockets.exceptions import ConnectionClosedError

from app.modules.providers import flow_ws_server
from app.modules.providers.errors import ExtensionNotConnectedError
from app.modules.providers.flow_extension import FlowExtensionBridge
from app.modules.providers.flow_ws_server import (
    EXTENSION_ORIGIN_PATTERN,
    MAX_MESSAGE_BYTES,
    PONG_MESSAGE,
    FlowWsServer,
)

TEST_PORT = 5074
REPLY = {"id": "request-1", "status": 200, "data": "answer"}


@dataclass
class FakeConnection:
    messages: list[str]
    closes_with_error: bool = False
    is_closed: bool = False
    sent_messages: list[str] = field(default_factory=list)

    def __iter__(self):
        yield from self.messages
        if self.closes_with_error:
            raise ConnectionClosedError(None, None)

    def send(self, message: str) -> None:
        if self.is_closed:
            raise ConnectionClosedError(None, None)
        self.sent_messages.append(message)


@dataclass
class ServerRig:
    serve: MagicMock
    server: MagicMock
    bridge: MagicMock
    ws_server: FlowWsServer

    def connection_handler(self) -> Callable[[FakeConnection], None]:
        return self.serve.call_args.args[0]


@pytest.fixture
def rig(monkeypatch):
    server = MagicMock()
    serve = MagicMock(return_value=server)
    monkeypatch.setattr(flow_ws_server, "serve", serve)
    bridge = MagicMock(spec=FlowExtensionBridge)
    return ServerRig(serve, server, bridge, FlowWsServer(bridge, TEST_PORT))


@pytest.fixture
def started_and_stopped(rig):
    rig.ws_server.start()
    rig.ws_server.stop()
    rig.ws_server.stop()
    return rig


@pytest.fixture
def port_in_use(rig, caplog):
    rig.serve.side_effect = OSError("address already in use")
    with caplog.at_level(logging.ERROR):
        rig.ws_server.start()
    rig.ws_server.stop()
    return SimpleNamespace(rig=rig, messages=[record.getMessage() for record in caplog.records])


@pytest.fixture
def origin_matches():
    return (
        EXTENSION_ORIGIN_PATTERN.fullmatch("chrome-extension://abcdefghijklmnopabcdefghijklmnop")
        is not None,
        EXTENSION_ORIGIN_PATTERN.fullmatch("http://localhost:4021") is not None,
    )


@pytest.fixture
def handled_connection(rig):
    rig.ws_server.start()
    connection = FakeConnection(
        [
            json.dumps({"type": "ping"}),
            json.dumps({"type": "extension_ready", "extensionVersion": "0.5.2"}),
            json.dumps({"type": "token_captured", "flowKey": "ya29.secret"}),
            json.dumps({"type": "netlog", "url": "https://flow.google.com/_/x"}),
            json.dumps(REPLY),
            json.dumps({"status": 200}),
            json.dumps([1, 2]),
            "not json",
        ],
        closes_with_error=True,
    )
    rig.connection_handler()(connection)
    rig.ws_server.stop()
    registered_sender = rig.bridge.register_connection.call_args.args[0]
    return SimpleNamespace(rig=rig, connection=connection, registered_sender=registered_sender)


@pytest.fixture
def sent_command(handled_connection):
    handled_connection.registered_sender({"type": "open_flow_tab"})
    return handled_connection.connection.sent_messages[-1]


@pytest.fixture
def closed_connection_error(handled_connection):
    handled_connection.connection.is_closed = True
    with pytest.raises(ExtensionNotConnectedError) as caught:
        handled_connection.registered_sender({"type": "open_flow_tab"})
    return caught.value


def test_start_listens_on_loopback_for_the_extension_only(started_and_stopped):
    assert started_and_stopped.serve.call_args.args[1:] == ("127.0.0.1", TEST_PORT)
    assert started_and_stopped.serve.call_args.kwargs == {
        "origins": [EXTENSION_ORIGIN_PATTERN],
        "max_size": MAX_MESSAGE_BYTES,
    }


def test_stop_shuts_the_server_down_once(started_and_stopped):
    assert started_and_stopped.server.serve_forever.call_count == 1
    assert started_and_stopped.server.shutdown.call_count == 1


def test_a_busy_port_is_logged_and_nothing_runs(port_in_use):
    assert port_in_use.messages == ["Flow extension server could not listen on port 5074"]
    assert port_in_use.rig.server.shutdown.call_count == 0


def test_extension_origin_pattern_accepts_only_extension_ids(origin_matches):
    assert origin_matches == (True, False)


def test_ping_is_answered_with_pong(handled_connection):
    assert handled_connection.connection.sent_messages == [PONG_MESSAGE]


def test_only_replies_reach_the_bridge(handled_connection):
    assert handled_connection.rig.bridge.receive_reply.call_count == 1
    assert handled_connection.rig.bridge.receive_reply.call_args.args == (REPLY,)


def test_the_connection_is_registered_until_it_closes(handled_connection):
    assert handled_connection.rig.bridge.unregister_connection.call_args.args == (
        handled_connection.registered_sender,
    )


def test_registered_sender_writes_json(sent_command):
    assert json.loads(sent_command) == {"type": "open_flow_tab"}


def test_registered_sender_reports_a_closed_connection(closed_connection_error):
    assert str(closed_connection_error) == "The Google Flow extension is not connected"
