from bisect import bisect_right
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from app.modules.jobs.video_to_markdown.moments import KeyMoment
from app.modules.jobs.video_to_markdown.transcript import (
    Transcript,
    TranscriptSegment,
    format_timestamp,
    join_segment_texts,
)

ALT_TEXT_FORBIDDEN_CHARS = str.maketrans({"[": "(", "]": ")"})
SPEAKERS_HEADING = "Speakers:"


@dataclass(frozen=True)
class CapturedMoment:
    moment: KeyMoment
    image_relative_path: str


@dataclass(frozen=True)
class Speaker:
    name: str
    voice: str


@dataclass(frozen=True)
class SpeakerVoices:
    speakers: Sequence[Speaker] = ()
    speaker_names_by_start_ms: Mapping[int, str] = field(default_factory=dict)


@dataclass(frozen=True)
class MarkdownSource:
    title: str
    summary: str
    source_label: str
    duration_ms: int
    transcript: Transcript
    captured_moments: list[CapturedMoment]
    voices: SpeakerVoices = SpeakerVoices()


@dataclass(frozen=True)
class _SectionStyle:
    render_heading_timestamp: Callable[[int], str]
    render_segments: Callable[[list[TranscriptSegment]], str]


@dataclass(frozen=True)
class _Section:
    captured_moment: CapturedMoment
    segments: list[TranscriptSegment]


def build_markdown(source: MarkdownSource) -> str:
    return _build(source, format_timestamp)


def build_markdown_with_moment_links(
    source: MarkdownSource, to_moment_url: Callable[[int], str]
) -> str:
    return _build(source, lambda at_ms: f"[{format_timestamp(at_ms)}]({to_moment_url(at_ms)})")


def _build(source: MarkdownSource, render_heading_timestamp: Callable[[int], str]) -> str:
    leading_segments, sections = _group_segments_by_moment(
        source.transcript.segments, source.captured_moments
    )
    render_segments = _to_segment_renderer(source.voices)
    blocks = [f"# {source.title}", _render_source_line(source)]
    if source.summary:
        blocks.append(source.summary)
    if source.voices.speakers:
        blocks.append(_render_speakers(source.voices.speakers))
    if leading_segments:
        blocks.append(render_segments(leading_segments))
    style = _SectionStyle(render_heading_timestamp, render_segments)
    blocks.extend(_render_section(section, style) for section in sections)
    return "\n\n".join(blocks) + "\n"


def _render_source_line(source: MarkdownSource) -> str:
    return (
        f"> Source: {source.source_label} · "
        f"Duration: {format_timestamp(source.duration_ms)} · "
        f"Language: {source.transcript.language}"
    )


def _render_speakers(speakers: Sequence[Speaker]) -> str:
    lines = [SPEAKERS_HEADING]
    for speaker in speakers:
        voice_part = f" — {speaker.voice}" if speaker.voice else ""
        lines.append(f"- **{speaker.name}**{voice_part}")
    return "\n".join(lines)


def _to_segment_renderer(
    voices: SpeakerVoices,
) -> Callable[[list[TranscriptSegment]], str]:
    if not voices.speakers:
        return join_segment_texts
    return lambda segments: _render_spoken_paragraphs(segments, voices.speaker_names_by_start_ms)


def _render_spoken_paragraphs(
    segments: list[TranscriptSegment], speaker_names_by_start_ms: Mapping[int, str]
) -> str:
    paragraphs = []
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        speaker_name = speaker_names_by_start_ms.get(segment.start_ms)
        paragraphs.append(f"**{speaker_name}:** {text}" if speaker_name else text)
    return "\n\n".join(paragraphs)


def _render_section(section: _Section, style: _SectionStyle) -> str:
    moment = section.captured_moment.moment
    heading = f"{style.render_heading_timestamp(moment.at_ms)} — {moment.title}"
    alt_text = f"{format_timestamp(moment.at_ms)} — {moment.title}".translate(
        ALT_TEXT_FORBIDDEN_CHARS
    )
    lines = [f"## {heading}", "", f"![{alt_text}]({section.captured_moment.image_relative_path})"]
    if section.segments:
        lines += ["", style.render_segments(section.segments)]
    return "\n".join(lines)


def _group_segments_by_moment(
    segments: list[TranscriptSegment], captured_moments: list[CapturedMoment]
) -> tuple[list[TranscriptSegment], list[_Section]]:
    moment_starts_ms = [captured.moment.at_ms for captured in captured_moments]
    sections = [_Section(captured_moment=captured, segments=[]) for captured in captured_moments]
    leading_segments: list[TranscriptSegment] = []
    for segment in segments:
        section_index = bisect_right(moment_starts_ms, segment.start_ms) - 1
        if section_index < 0:
            leading_segments.append(segment)
            continue
        sections[section_index].segments.append(segment)
    return leading_segments, sections
