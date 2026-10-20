from pathlib import Path

import pytest

from app.modules.jobs.film_analysis.audio_notes import (
    AudioNotes,
    AudioPartReply,
    HeardSound,
    SoundKind,
    SpeakerLine,
    audio_notes_to_json,
    normalize_audio_replies,
    to_sound_title,
    to_speaker_lines,
    to_speaker_voices,
)
from app.modules.jobs.film_analysis.media_parts import (
    MediaPart,
    find_part_paths,
    group_segments_by_part,
    to_media_parts,
    to_part_label,
)
from app.modules.jobs.video_to_markdown.markdown import Speaker, SpeakerVoices
from app.modules.jobs.video_to_markdown.transcript import TranscriptSegment

ONLY_PART = MediaPart(path=Path("audio/part-01.m4a"), start_ms=0, end_ms=120_000)
TC_AIM_29_REPLY = {
    "speakers": [
        {"name": " Mai ", "voice": "soft"},
        {"name": "mai", "voice": "loud"},
        {"name": "", "voice": "x"},
    ],
    "lines": [
        {"atMs": 1000, "speaker": "Mai"},
        {"atMs": 1000, "speaker": "Long"},
        {"atMs": 4000, "speaker": "Mai"},
        {"atMs": 5000, "speaker": "Ba"},
        {"atMs": 9000, "speaker": " "},
    ],
    "sounds": [
        {"atMs": 20000, "kind": "ambient", "description": "a dog barks"},
        {"atMs": 21000, "kind": "action", "description": "a door slams"},
        {"atMs": 30000, "kind": "laugh", "description": "x"},
        {"atMs": 40000, "kind": "music", "description": " "},
        {"atMs": 500000, "kind": "silence", "description": "silence"},
    ],
}
SECOND_PART = MediaPart(path=Path("audio/part-02.m4a"), start_ms=120_000, end_ms=180_000)
SEGMENTS = [
    TranscriptSegment(start_ms=-200, end_ms=900, text=" Early."),
    TranscriptSegment(start_ms=10_000, end_ms=12_000, text=" One."),
    TranscriptSegment(start_ms=1_810_000, end_ms=1_812_000, text=" Two."),
    TranscriptSegment(start_ms=3_700_000, end_ms=3_702_000, text=" Three."),
]


def build_part_reply(part: MediaPart, segment_starts_ms: set[int], reply) -> AudioPartReply:
    return AudioPartReply(part=part, segment_starts_ms=frozenset(segment_starts_ms), reply=reply)


@pytest.fixture
def tc_aim_29_notes():
    return normalize_audio_replies(
        [build_part_reply(ONLY_PART, {1000, 5000, 9000}, TC_AIM_29_REPLY)], 120_000
    )


@pytest.fixture
def two_part_notes():
    return normalize_audio_replies(
        [
            build_part_reply(
                ONLY_PART,
                {1000},
                {
                    "speakers": [],
                    "lines": [{"atMs": 1000, "speaker": "LAN"}],
                    "sounds": [{"atMs": -50, "kind": "music", "description": " drums " * 60}],
                },
            ),
            build_part_reply(
                SECOND_PART,
                {130_000},
                {
                    "speakers": [{"name": "Lan", "voice": "old woman"}, {"name": "N" * 120}],
                    "lines": [{"atMs": 130_000.0, "speaker": "lan"}],
                    "sounds": [{"atMs": 90_000, "kind": "action", "description": "a door slams"}],
                },
            ),
        ],
        600_000,
    )


@pytest.fixture(
    params=[
        "not an object",
        {"speakers": "Mai", "lines": None, "sounds": [3, "x"]},
        {
            "speakers": [{"name": 7}],
            "lines": [{"atMs": True, "speaker": "Mai"}, {"atMs": "1000", "speaker": "Mai"}],
            "sounds": [{"atMs": None, "kind": "ambient", "description": "rain"}],
        },
    ]
)
def malformed_reply_notes(request):
    reply = request.param if isinstance(request.param, dict) else {}
    return normalize_audio_replies([build_part_reply(ONLY_PART, {1000}, reply)], 120_000)


def test_speakers_are_trimmed_and_a_repeat_or_blank_name_is_dropped(tc_aim_29_notes):
    assert tc_aim_29_notes.speakers == [Speaker("Mai", "soft"), Speaker("Ba", "")]


def test_lines_keep_the_first_entry_of_a_segment_start(tc_aim_29_notes):
    assert tc_aim_29_notes.lines == [SpeakerLine(1000, "Mai"), SpeakerLine(5000, "Ba")]


def test_sounds_are_clamped_and_spaced_and_unknown_or_blank_ones_dropped(tc_aim_29_notes):
    assert tc_aim_29_notes.sounds == [
        HeardSound(20_000, SoundKind.AMBIENT, "a dog barks"),
        HeardSound(119_500, SoundKind.SILENCE, "silence"),
    ]


def test_a_speaker_of_a_later_part_gives_its_voice_to_an_earlier_line(two_part_notes):
    assert two_part_notes.speakers == [Speaker("Lan", "old woman"), Speaker("N" * 100, "")]
    assert two_part_notes.lines == [SpeakerLine(1000, "Lan"), SpeakerLine(130_000, "Lan")]


def test_a_sound_is_clamped_to_its_part_and_its_description_cut(two_part_notes):
    assert two_part_notes.sounds == [
        HeardSound(0, SoundKind.MUSIC, ("drums  " * 60).strip()[:200]),
        HeardSound(120_000, SoundKind.ACTION, "a door slams"),
    ]


def test_a_malformed_reply_finds_nothing(malformed_reply_notes):
    assert malformed_reply_notes == AudioNotes(speakers=[], lines=[], sounds=[])


def test_audio_notes_are_saved_as_json(tc_aim_29_notes):
    assert audio_notes_to_json(tc_aim_29_notes) == {
        "speakers": [{"name": "Mai", "voice": "soft"}, {"name": "Ba", "voice": ""}],
        "lines": [{"atMs": 1000, "speaker": "Mai"}, {"atMs": 5000, "speaker": "Ba"}],
        "sounds": [
            {"atMs": 20_000, "kind": "ambient", "description": "a dog barks"},
            {"atMs": 119_500, "kind": "silence", "description": "silence"},
        ],
    }


def test_speaker_lines_leave_out_a_blank_voice(tc_aim_29_notes):
    assert to_speaker_lines(tc_aim_29_notes.speakers) == ["- Mai — soft", "- Ba"]


def test_speaker_voices_map_each_line_start_to_its_speaker(tc_aim_29_notes):
    assert to_speaker_voices(tc_aim_29_notes) == SpeakerVoices(
        speakers=tc_aim_29_notes.speakers, speaker_names_by_start_ms={1000: "Mai", 5000: "Ba"}
    )


def test_a_sound_frame_is_titled_with_its_kind_label():
    assert [
        to_sound_title(HeardSound(0, kind, "x"))
        for kind in (SoundKind.ACTION, SoundKind.SILENCE, SoundKind.AMBIENT, SoundKind.MUSIC)
    ] == ["Action: x", "Silence: x", "Ambient: x", "Music: x"]


@pytest.fixture
def part_dir(tmp_path):
    for name in ("part-02.m4a", "part-01.m4a", "notes.txt"):
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "part-03").mkdir()
    return tmp_path


def test_find_part_paths_lists_part_files_in_order(part_dir):
    assert find_part_paths(part_dir) == [part_dir / "part-01.m4a", part_dir / "part-02.m4a"]


def test_find_part_paths_of_a_missing_folder_is_empty(tmp_path):
    assert find_part_paths(tmp_path / "absent") == []


def test_media_parts_follow_each_other():
    assert to_media_parts(
        [Path("p1"), Path("p2"), Path("p3")], [1_800_000, 1_800_000, 600_000]
    ) == [
        MediaPart(Path("p1"), 0, 1_800_000),
        MediaPart(Path("p2"), 1_800_000, 3_600_000),
        MediaPart(Path("p3"), 3_600_000, 4_200_000),
    ]


def test_no_part_paths_make_no_parts():
    assert to_media_parts([], []) == []


def test_segments_go_to_the_part_they_start_in():
    parts = to_media_parts([Path("p1"), Path("p2"), Path("p3")], [1_800_000, 1_800_000, 600_000])
    assert [
        [segment.text for segment in part_segments]
        for part_segments in group_segments_by_part(SEGMENTS, parts)
    ] == [[" Early.", " One."], [" Two."], [" Three."]]


def test_part_label_names_the_media_and_its_time_range():
    assert to_part_label("audio", MediaPart(Path("p2"), 1_800_000, 3_600_000)) == (
        "[audio 30:00–1:00:00]"
    )
