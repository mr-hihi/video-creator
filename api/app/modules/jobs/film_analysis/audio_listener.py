import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.common.process import CommandError
from app.modules.ai_models.ai_caller import AiCaller
from app.modules.ai_models.ai_calls import (
    AiAsk,
    AiLimits,
    AiModelChoice,
    AiStepGroup,
    AttachedMedia,
)
from app.modules.jobs.film_analysis.audio_notes import (
    SPEAKERS_AND_SOUNDS_SCHEMA,
    AudioNotes,
    AudioPartReply,
    audio_notes_to_json,
    normalize_audio_replies,
    to_speaker_lines,
)
from app.modules.jobs.film_analysis.media_parts import (
    AUDIO_MEDIA_WORD,
    AUDIO_MIME_TYPE,
    MediaPart,
    find_part_paths,
    group_segments_by_part,
    to_media_parts,
    to_part_label,
)
from app.modules.jobs.job_prompts import get_job_prompt
from app.modules.jobs.models import Job, JobStep
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.storage import JobStorage
from app.modules.jobs.video_to_markdown.ffmpeg_media import AudioSplit, FfmpegMediaProcessor
from app.modules.jobs.video_to_markdown.moment_steps import to_transcript_lines
from app.modules.jobs.video_to_markdown.transcript import TranscriptSegment, format_timestamp
from app.modules.prompt_presets.prompt_texts import (
    AudioPartRequestText,
    PromptKey,
    build_audio_part_message,
)

AUDIO_PREPARATION_FAILED_MESSAGE = "Audio preparation failed: {error}"
NO_AUDIO_PART_ERROR = "ffmpeg wrote no audio part"


class AudioPreparationError(Exception):
    pass


@dataclass(frozen=True)
class AudioListenerTools:
    storage: JobStorage
    repository: JobRepository
    media: FfmpegMediaProcessor
    ai_caller: AiCaller


@dataclass(frozen=True)
class AudioListenerConfig:
    part_sec: int
    limits: AiLimits


@dataclass(frozen=True)
class AudioSource:
    job: Job
    video_path: Path
    segments: Sequence[TranscriptSegment]
    duration_ms: int


@dataclass(frozen=True)
class AudioPartRequest:
    instructions: str
    part: MediaPart
    segments: Sequence[TranscriptSegment]
    speaker_lines: Sequence[str]


class AudioListener:
    def __init__(self, tools: AudioListenerTools, config: AudioListenerConfig):
        self._tools = tools
        self._config = config

    def listen(self, source: AudioSource, report_step: Callable[[JobStep], None]) -> AudioNotes:
        report_step(JobStep.LISTENING_TO_AUDIO)
        job_id = source.job.id
        choice = self._tools.ai_caller.find_google_model(AiStepGroup.AUDIO)
        notes_path = self._tools.storage.audio_notes_path(job_id)
        notes_path.unlink(missing_ok=True)
        try:
            parts = self._split_audio(job_id, source.video_path)
            self._tools.repository.save_ai_used(job_id, JobStep.LISTENING_TO_AUDIO, choice)
            replies = self._ask_every_part(source, choice, parts)
        finally:
            self._tools.storage.delete_audio_parts(job_id)
        notes = normalize_audio_replies(replies, source.duration_ms)
        notes_path.write_text(
            json.dumps(audio_notes_to_json(notes), ensure_ascii=False), encoding="utf-8"
        )
        return notes

    def _split_audio(self, job_id: str, video_path: Path) -> list[MediaPart]:
        audio_dir = self._tools.storage.audio_dir(job_id)
        self._tools.storage.delete_audio_parts(job_id)
        audio_dir.mkdir(parents=True)
        try:
            self._tools.media.split_audio(
                AudioSplit(
                    video_path=video_path, output_dir=audio_dir, part_sec=self._config.part_sec
                )
            )
            part_paths = find_part_paths(audio_dir)
            if not part_paths:
                raise CommandError(NO_AUDIO_PART_ERROR)
            durations_ms = [self._tools.media.probe_duration_ms(path) for path in part_paths]
        except CommandError as error:
            raise AudioPreparationError(
                AUDIO_PREPARATION_FAILED_MESSAGE.format(error=error)
            ) from error
        return to_media_parts(part_paths, durations_ms)

    def _ask_every_part(
        self, source: AudioSource, choice: AiModelChoice, parts: Sequence[MediaPart]
    ) -> list[AudioPartReply]:
        instructions = get_job_prompt(source.job.options, PromptKey.SPEAKERS_AND_SOUNDS)
        replies: list[AudioPartReply] = []
        for part, segments in zip(
            parts, group_segments_by_part(source.segments, parts), strict=True
        ):
            speakers_so_far = normalize_audio_replies(replies, source.duration_ms).speakers
            reply = self._tools.ai_caller.ask_for_json(
                choice,
                to_audio_part_ask(
                    AudioPartRequest(
                        instructions=instructions,
                        part=part,
                        segments=segments,
                        speaker_lines=to_speaker_lines(speakers_so_far),
                    )
                ),
                self._config.limits,
            )
            replies.append(
                AudioPartReply(
                    part=part,
                    segment_starts_ms=frozenset(segment.start_ms for segment in segments),
                    reply=reply,
                )
            )
        return replies


def to_audio_part_ask(request: AudioPartRequest) -> AiAsk:
    part = request.part
    return AiAsk(
        instructions=request.instructions,
        message=build_audio_part_message(
            AudioPartRequestText(
                start=format_timestamp(part.start_ms),
                end=format_timestamp(part.end_ms),
                speaker_lines=request.speaker_lines,
                transcript_lines=to_transcript_lines(request.segments),
            )
        ),
        reply_schema=SPEAKERS_AND_SOUNDS_SCHEMA,
        media=[
            AttachedMedia(
                label=to_part_label(AUDIO_MEDIA_WORD, part),
                path=part.path,
                mime_type=AUDIO_MIME_TYPE,
            )
        ],
    )
