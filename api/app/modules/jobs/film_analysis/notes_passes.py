from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.modules.jobs.models import Job, JobStep
from app.modules.jobs.video_to_markdown.markdown import CapturedMoment


@dataclass(frozen=True)
class WrittenNotes:
    video_notes: str
    captured_moments: Sequence[CapturedMoment]


class NotesPasses(Protocol):
    def run(
        self, job: Job, notes: WrittenNotes, report_step: Callable[[JobStep], None]
    ) -> None: ...
