from types import SimpleNamespace

import pytest

from app.modules.film_clones.clone_replies import (
    ExpectedScript,
    FrameInfo,
    find_unmatched_frames,
    join_batch_replies,
    normalize_assets,
    normalize_localization,
    normalize_script,
    normalize_shots,
)
from app.modules.film_clones.errors import CloneStepFailedError
from app.modules.film_clones.models import AssetKind, CameraAngle, FrameKind, ShotSize

JOB_FRAMES = ["images/moment-01-00m05s.jpg", "images/moment-02-00m40s.jpg"]
FRAMES = [
    FrameInfo("images/moment-01-00m05s.jpg", 5000, FrameKind.DIALOGUE),
    FrameInfo("images/moment-02-00m40s.jpg", 40000, FrameKind.SCENE),
]


@pytest.fixture
def assets():
    return normalize_assets(
        {
            "assets": [
                {
                    "kind": "character",
                    "name": " Min-jun ",
                    "description": "A young scholar in a white hanbok",
                    "culture": "Korean",
                    "period": "Joseon dynasty (1392–1897)",
                    "frames": ["moment-01-00m05s.jpg", "images/unknown.jpg", JOB_FRAMES[0]],
                },
                {"kind": "character", "name": "MIN-JUN", "description": "Repeat"},
                {"kind": "vehicle", "name": "Cart", "description": "Unknown kind"},
                {"kind": "prop", "name": "   ", "description": "Blank name"},
                {"kind": "location", "name": "Palace", "description": "", "culture": " "},
            ]
        },
        JOB_FRAMES,
    )


@pytest.fixture
def capped_assets():
    reply = {
        "assets": [
            {"kind": "prop", "name": f"Prop {index}", "description": "A prop"}
            for index in range(70)
        ]
    }
    return normalize_assets(reply, JOB_FRAMES)


@pytest.fixture
def shots():
    return normalize_shots(
        {
            "shots": [
                {
                    "frame": "moment-01-00m05s.jpg",
                    "shotSize": "close_up",
                    "cameraAngle": "low",
                    "emotion": "  Afraid ",
                    "action": "Runs to the gate",
                    "assetNames": ["palace", "Nobody", "Palace", "Min-jun (Character)"],
                },
                {"frame": JOB_FRAMES[0], "shotSize": "wide", "cameraAngle": "high"},
                {"frame": "images/unknown.jpg", "shotSize": "wide"},
            ]
        },
        FRAMES,
        ["Min-jun", "Palace"],
    )


@pytest.fixture
def unmatched_frames():
    return find_unmatched_frames(
        {
            "shots": [
                {"frame": "moment-01-00m05s.jpg"},
                {"frame": "Frame 2"},
                {"frame": JOB_FRAMES[1]},
                {"frame": "images/unknown.jpg"},
            ]
        },
        FRAMES,
    )


@pytest.fixture
def odd_shot():
    (shot, _) = normalize_shots(
        {"shots": [{"frame": JOB_FRAMES[0], "shotSize": "huge", "cameraAngle": "sideways"}]},
        FRAMES,
        [],
    )
    return shot


@pytest.fixture
def proposals():
    return normalize_localization(
        {
            "assets": [
                {
                    "name": "min-jun",
                    "changed": True,
                    "localizedName": " ",
                    "localizedDescription": "A young Vietnamese scholar in an ao dai",
                    "note": "Vietnamese scholars wore ao dai",
                },
                {"name": "Min-jun", "changed": True, "localizedDescription": "Repeat"},
                {"name": "Palace", "changed": True, "localizedName": "Hue citadel"},
                {"name": "Stranger", "changed": True, "localizedDescription": "Dropped"},
                {
                    "name": "Fan (prop)",
                    "changed": True,
                    "localizedName": "Uchiwa (prop)",
                    "localizedDescription": "A paper uchiwa fan",
                },
            ]
        },
        ["Min-jun", "Palace", "Fan", "Lamp"],
    )


@pytest.fixture
def script():
    return normalize_script(
        {
            "title": "  ",
            "logline": " A scholar flees ",
            "scenes": [
                {
                    "shotId": "shot-1",
                    "description": " He runs. ",
                    "dialogue": "  ",
                    "imagePrompt": "A scholar running",
                },
                {"shotId": "shot-1", "description": "Repeat", "imagePrompt": "Repeat"},
                {"shotId": "shot-9", "description": "Unknown", "imagePrompt": "Unknown"},
                {
                    "shotId": "shot-2",
                    "description": "x" * 2100,
                    "dialogue": "Lan: Đi thôi.",
                    "imagePrompt": "y" * 4100,
                },
            ],
        },
        ExpectedScript(["shot-1", "shot-2"], "palace-escape", "claude"),
    )


@pytest.fixture
def missing_scene_error():
    with pytest.raises(CloneStepFailedError) as caught:
        normalize_script(
            {
                "title": "T",
                "scenes": [
                    {"shotId": "shot-1", "description": "Ok", "imagePrompt": "Ok"},
                    {"shotId": "shot-2", "description": "", "imagePrompt": "Blank description"},
                ],
            },
            ExpectedScript(["shot-1", "shot-2", "shot-3"], "fallback", "gemini"),
        )
    return caught.value


def test_assets_keep_valid_unique_entries_in_reply_order(assets):
    assert [(asset.kind, asset.name) for asset in assets] == [
        (AssetKind.CHARACTER, "Min-jun"),
        (AssetKind.LOCATION, "Palace"),
    ]


def test_asset_frames_keep_only_job_frames_once(assets):
    assert assets[0].frames == ["images/moment-01-00m05s.jpg"]


def test_blank_origin_becomes_unknown(assets):
    palace = assets[1]
    assert palace.culture == "Unknown"
    assert palace.period == "Unknown"
    assert palace.description == "Palace"


def test_only_the_first_60_assets_are_kept(capped_assets):
    assert len(capped_assets) == 60
    assert capped_assets[-1].name == "Prop 59"


def test_every_frame_becomes_one_shot_with_the_first_reply_entry(shots):
    first, second = shots
    assert first.frame == FRAMES[0]
    assert first.shot_size is ShotSize.CLOSE_UP
    assert first.camera_angle is CameraAngle.LOW
    assert first.emotion == "Afraid"
    assert first.asset_names == ["Palace", "Min-jun"]
    assert second.frame == FRAMES[1]
    assert (second.shot_size, second.camera_angle, second.emotion, second.action) == (
        None,
        None,
        None,
        None,
    )


def test_unmatched_reply_frames_are_listed(unmatched_frames):
    assert unmatched_frames == ["Frame 2", "images/unknown.jpg"]


def test_values_outside_the_lists_become_null(odd_shot):
    assert odd_shot.shot_size is None
    assert odd_shot.camera_angle is None


def test_localization_matches_candidates_and_fills_blanks(proposals):
    min_jun = proposals["Min-jun"]
    assert min_jun.changed is True
    assert min_jun.localized_name == "Min-jun"
    assert min_jun.localized_description == "A young Vietnamese scholar in an ao dai"
    assert min_jun.note == "Vietnamese scholars wore ao dai"


def test_change_without_description_or_missing_candidate_is_not_changed(proposals):
    assert proposals["Palace"].changed is False
    assert proposals["Palace"].localized_name is None
    assert proposals["Lamp"].changed is False
    assert set(proposals) == {"Min-jun", "Palace", "Fan", "Lamp"}


def test_name_echoed_with_its_kind_still_matches(proposals):
    assert proposals["Fan"].changed is True
    assert proposals["Fan"].localized_name == "Uchiwa"


def test_script_keeps_the_first_scene_per_known_shot(script):
    first = script.scenes_by_shot_id["shot-1"]
    assert set(script.scenes_by_shot_id) == {"shot-1", "shot-2"}
    assert first.description == "He runs."
    assert first.dialogue is None


def test_script_text_is_cut_and_blank_title_falls_back(script):
    second = script.scenes_by_shot_id["shot-2"]
    assert len(second.description) == 2000
    assert len(second.image_prompt) == 4000
    assert second.dialogue == "Lan: Đi thôi."
    assert script.title == "palace-escape"
    assert script.logline == "A scholar flees"


def test_shot_left_without_a_scene_fails_the_step(missing_scene_error):
    assert str(missing_scene_error) == "gemini returned no scene for 2 of 3 shots"


@pytest.fixture
def long_title_script():
    return SimpleNamespace(
        script=normalize_script(
            {
                "title": "t" * 200,
                "scenes": [{"shotId": "s", "description": "d", "imagePrompt": "p"}],
            },
            ExpectedScript(["s"], "fallback", "claude"),
        )
    )


def test_title_is_cut_to_150_characters(long_title_script):
    assert len(long_title_script.script.title) == 150
    assert long_title_script.script.logline is None


@pytest.fixture
def joined_replies():
    return join_batch_replies(
        [
            {"title": "First", "scenes": [{"shotId": "s-1"}]},
            {"title": "Second", "scenes": [{"shotId": "s-2"}, "not an entry"]},
            {"title": "Third", "scenes": "not a list"},
        ],
        "scenes",
    )


def test_joined_replies_keep_the_first_reply_and_every_list_entry(joined_replies):
    assert joined_replies == {"title": "First", "scenes": [{"shotId": "s-1"}, {"shotId": "s-2"}]}


def test_joining_no_reply_gives_an_empty_list():
    assert join_batch_replies([], "shots") == {"shots": []}
