from collections.abc import Callable
from types import SimpleNamespace

import pytest

from app.modules.providers.errors import ExtensionNotConnectedError
from app.modules.providers.flow_extension import FlowExtensionBridge

METHOD = "batch_rpc"
PARAMS = {"rpcid": "jwpduf", "freq": "[]"}
SHORT_TIMEOUT_SEC = 0.01


def capture(error_type: type[Exception], call: Callable[[], object]) -> Exception:
    with pytest.raises(error_type) as caught:
        call()
    return caught.value


@pytest.fixture
def bridge():
    return FlowExtensionBridge()


@pytest.fixture
def unconnected_call_error(bridge):
    return capture(ExtensionNotConnectedError, lambda: bridge.call(METHOD, PARAMS, 1))


@pytest.fixture
def answered_call(bridge):
    commands = []

    def answer(command):
        commands.append(command)
        bridge.receive_reply({"id": command["id"], "status": 200, "data": "ok"})

    bridge.register_connection(answer)
    reply = bridge.call(METHOD, PARAMS, 1)
    return SimpleNamespace(reply=reply, command=commands[0])


@pytest.fixture
def unanswered_call_error(bridge):
    bridge.register_connection(lambda command: None)
    return capture(TimeoutError, lambda: bridge.call(METHOD, PARAMS, SHORT_TIMEOUT_SEC))


@pytest.fixture
def dropped_call(bridge):
    def drop_connection(command):
        bridge.unregister_connection(drop_connection)

    bridge.register_connection(drop_connection)
    error = capture(ExtensionNotConnectedError, lambda: bridge.call(METHOD, PARAMS, 1))
    return SimpleNamespace(error=error, is_connected=bridge.is_connected())


@pytest.fixture
def failed_send_call(bridge):
    commands = []

    def fail_to_send(command):
        commands.append(command)
        raise ExtensionNotConnectedError()

    bridge.register_connection(fail_to_send)
    error = capture(ExtensionNotConnectedError, lambda: bridge.call(METHOD, PARAMS, 1))
    bridge.receive_reply({"id": commands[0]["id"], "status": 200})
    return SimpleNamespace(error=error, command_count=len(commands))


@pytest.fixture
def last_connection_call(bridge):
    first_commands = []
    last_commands = []
    other_sender = first_commands.append

    def answer_after_other_leaves(command):
        last_commands.append(command)
        bridge.unregister_connection(other_sender)
        bridge.receive_reply({"id": command["id"], "status": 200})

    bridge.register_connection(other_sender)
    bridge.register_connection(answer_after_other_leaves)
    reply = bridge.call(METHOD, PARAMS, 1)
    return SimpleNamespace(reply=reply, first_commands=first_commands, last_commands=last_commands)


@pytest.fixture
def unknown_sender_removal(bridge):
    bridge.register_connection(lambda command: None)
    bridge.unregister_connection(lambda command: None)
    bridge.receive_reply({"id": "never-sent", "status": 200})
    return bridge.is_connected()


def test_call_needs_a_connection(unconnected_call_error):
    assert str(unconnected_call_error) == "The Google Flow extension is not connected"


def test_call_sends_the_command_and_returns_the_reply(answered_call):
    assert answered_call.command["method"] == METHOD
    assert answered_call.command["params"] == PARAMS
    assert answered_call.reply == {"id": answered_call.command["id"], "status": 200, "data": "ok"}


def test_call_times_out_without_a_reply(unanswered_call_error):
    assert str(unanswered_call_error) == (
        "The Google Flow extension did not answer batch_rpc in 0.01 s"
    )


def test_call_fails_when_its_connection_closes(dropped_call):
    assert str(dropped_call.error) == "The Google Flow extension is not connected"
    assert dropped_call.is_connected is False


def test_call_fails_when_the_command_cannot_be_sent(failed_send_call):
    assert isinstance(failed_send_call.error, ExtensionNotConnectedError)
    assert failed_send_call.command_count == 1


def test_call_goes_through_the_last_connection(last_connection_call):
    assert last_connection_call.first_commands == []
    assert len(last_connection_call.last_commands) == 1
    assert last_connection_call.reply["status"] == 200


def test_unknown_sender_and_reply_change_nothing(unknown_sender_removal):
    assert unknown_sender_removal is True
