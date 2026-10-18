import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime

from app.db import utc_now
from app.modules.ai_models.ai_calls import AiModelChoice


@dataclass(frozen=True)
class AiActivity:
    choice: AiModelChoice
    started_at: datetime
    last_output_at: datetime | None


class AiActivityTracker:
    def __init__(self, clock: Callable[[], datetime] = utc_now):
        self._clock = clock
        self._activities_by_clone_id: dict[str, AiActivity] = {}
        self._lock = threading.Lock()

    def start(self, clone_id: str, choice: AiModelChoice) -> None:
        with self._lock:
            self._activities_by_clone_id[clone_id] = AiActivity(
                choice=choice, started_at=self._clock(), last_output_at=None
            )

    def record_output(self, clone_id: str) -> None:
        with self._lock:
            activity = self._activities_by_clone_id[clone_id]
            self._activities_by_clone_id[clone_id] = replace(activity, last_output_at=self._clock())

    def finish(self, clone_id: str) -> None:
        with self._lock:
            self._activities_by_clone_id.pop(clone_id, None)

    def get(self, clone_id: str) -> AiActivity | None:
        with self._lock:
            return self._activities_by_clone_id.get(clone_id)
