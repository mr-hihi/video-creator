from typing import Protocol

from app.modules.media_generation.media_task import MediaTask, PollOutcome, SubmitOutcome


class MediaProviderAdapter(Protocol):
    def submit(self, task: MediaTask) -> SubmitOutcome: ...

    def poll(self, task: MediaTask, external_id: str) -> PollOutcome: ...
