import threading
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.db import utc_now
from app.modules.providers.errors import ExtensionNotConnectedError

OPEN_FLOW_TAB_COMMAND = {"type": "open_flow_tab"}
REQUEST_ID_KEY = "id"
METHOD_KEY = "method"
PARAMS_KEY = "params"

CommandSender = Callable[[dict[str, Any]], None]


@dataclass
class _PendingCall:
    sender: CommandSender
    answer_event: threading.Event = field(default_factory=threading.Event)
    reply: dict[str, Any] | None = None


class FlowExtensionBridge:
    def __init__(self):
        self._lock = threading.Lock()
        self._command_senders: list[CommandSender] = []
        self._pending_calls_by_id: dict[str, _PendingCall] = {}
        self._paused_until: datetime | None = None

    def is_connected(self) -> bool:
        with self._lock:
            return bool(self._command_senders)

    def register_connection(self, send_command: CommandSender) -> None:
        with self._lock:
            self._command_senders.append(send_command)

    def unregister_connection(self, send_command: CommandSender) -> None:
        with self._lock:
            if send_command in self._command_senders:
                self._command_senders.remove(send_command)
            orphaned_calls = [
                pending_call
                for pending_call in self._pending_calls_by_id.values()
                if pending_call.sender is send_command
            ]
        for pending_call in orphaned_calls:
            pending_call.answer_event.set()

    def call(self, method: str, params: Mapping[str, Any], timeout_sec: float) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        pending_call = self._open_call(request_id)
        try:
            pending_call.sender(
                {REQUEST_ID_KEY: request_id, METHOD_KEY: method, PARAMS_KEY: dict(params)}
            )
            is_answered = pending_call.answer_event.wait(timeout_sec)
        finally:
            with self._lock:
                self._pending_calls_by_id.pop(request_id, None)
        if not is_answered:
            raise TimeoutError(
                f"The Google Flow extension did not answer {method} in {timeout_sec:g} s"
            )
        if pending_call.reply is None:
            raise ExtensionNotConnectedError()
        return pending_call.reply

    def receive_reply(self, reply: Mapping[str, Any]) -> None:
        with self._lock:
            pending_call = self._pending_calls_by_id.get(str(reply.get(REQUEST_ID_KEY)))
        if pending_call is None:
            return
        pending_call.reply = dict(reply)
        pending_call.answer_event.set()

    def pause_for(self, seconds: float) -> None:
        with self._lock:
            self._paused_until = utc_now() + timedelta(seconds=seconds)

    def paused_until(self) -> datetime | None:
        with self._lock:
            if self._paused_until is None or self._paused_until <= utc_now():
                return None
            return self._paused_until

    def resume(self) -> None:
        with self._lock:
            self._paused_until = None

    def open_flow_tab(self) -> None:
        with self._lock:
            senders = list(self._command_senders)
        if not senders:
            raise ExtensionNotConnectedError()
        senders[-1](OPEN_FLOW_TAB_COMMAND)

    def _open_call(self, request_id: str) -> _PendingCall:
        with self._lock:
            if not self._command_senders:
                raise ExtensionNotConnectedError()
            pending_call = _PendingCall(self._command_senders[-1])
            self._pending_calls_by_id[request_id] = pending_call
        return pending_call
