from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.films.errors import (
    FilmConflictError,
    InvalidFilmRequestError,
    StyleNotFoundError,
)
from app.modules.films.models import Style
from app.modules.films.repository import FilmRepository
from app.modules.films.style_service import (
    FilmStyleService,
    StyleChanges,
    StyleDraft,
    get_known_style,
)

NOIR = Style(
    id="noir-1",
    name="Noir",
    is_builtin=False,
    style_instruction="Black and white film noir",
    negative_prompt="NOT color",
    scene_prefix="Noir shot",
    lighting="Hard shadows",
)
ART = Style(id="art-1", name="Art", is_builtin=False, style_instruction="Art", lighting="L")
ANIME = Style(id="anime", name="Anime", is_builtin=True, style_instruction="A", lighting="L")
REALISTIC = Style(
    id="realistic", name="Photorealistic", is_builtin=True, style_instruction="R", lighting="L"
)
LEGACY = Style(id="legacy", name="Legacy", is_builtin=True, style_instruction="X", lighting="L")


def build_styles(styles=(), usage=(0, 0)):
    styles_by_id = {style.id: style for style in styles}
    repository = MagicMock(spec=FilmRepository)
    repository.find_style.side_effect = styles_by_id.get
    repository.find_style_by_name.side_effect = lambda name: next(
        (style for style in styles if style.name.casefold() == name.casefold()), None
    )
    repository.find_styles.return_value = list(styles)
    repository.add_style.side_effect = lambda style: style
    repository.count_style_usage.return_value = usage
    return SimpleNamespace(service=FilmStyleService(repository), repository=repository)


def capture(error_class, call):
    with pytest.raises(error_class) as caught:
        call()
    return caught.value


@pytest.fixture
def written_builtin_styles():
    styles = build_styles()
    styles.service.ensure_builtin_styles()
    rows = styles.repository.add_missing_styles.call_args.args[0]
    return SimpleNamespace(
        rows=rows,
        names=[row.name for row in rows],
        ids=[row.id for row in rows],
        builtin_flags={row.is_builtin for row in rows},
    )


@pytest.fixture
def listed_style_ids():
    styles = build_styles([LEGACY, ANIME, REALISTIC, ART, NOIR])
    return [style.id for style in styles.service.list_styles()]


@pytest.fixture
def created_style():
    styles = build_styles([NOIR])
    style = styles.service.create_style(
        StyleDraft(
            name="  Pastel  ",
            style_instruction=" Soft pastel colors ",
            negative_prompt="   ",
            scene_prefix=" Pastel scene ",
        )
    )
    return SimpleNamespace(style=style, id_length=len(style.id))


@pytest.fixture
def lit_style():
    styles = build_styles()
    return styles.service.create_style(
        StyleDraft(name="Neon", style_instruction="Neon signs", lighting=" Neon glow ")
    )


@pytest.fixture(
    params=[
        (StyleDraft(name="   ", style_instruction="x"), "Style name must be 1-50 characters"),
        (StyleDraft(name="n" * 51, style_instruction="x"), "Style name must be 1-50 characters"),
        (
            StyleDraft(name="Empty", style_instruction="  "),
            "Style instruction must be 1-2000 characters",
        ),
        (
            StyleDraft(name="Long", style_instruction="i" * 2001),
            "Style instruction must be 1-2000 characters",
        ),
        (
            StyleDraft(name="Neg", style_instruction="x", negative_prompt="n" * 1001),
            "Negative prompt must be at most 1000 characters",
        ),
        (
            StyleDraft(name="Pre", style_instruction="x", scene_prefix="p" * 501),
            "Scene prefix must be at most 500 characters",
        ),
        (
            StyleDraft(name="Lit", style_instruction="x", lighting="l" * 201),
            "Lighting must be at most 200 characters",
        ),
    ]
)
def invalid_style_outcome(request):
    draft, expected_message = request.param
    styles = build_styles()
    error = capture(InvalidFilmRequestError, lambda: styles.service.create_style(draft))
    return SimpleNamespace(actual=str(error), expected=expected_message)


@pytest.fixture
def duplicate_style_error():
    styles = build_styles([NOIR])
    return capture(
        FilmConflictError,
        lambda: styles.service.create_style(StyleDraft(name="noir", style_instruction="x")),
    )


@pytest.fixture
def updated_style():
    styles = build_styles([NOIR])
    styles.service.update_style(
        NOIR.id,
        StyleChanges(
            name=" NOIR ",
            style_instruction=" Grainy noir ",
            negative_prompt="",
            scene_prefix="",
            lighting="",
        ),
    )
    return styles.repository.update_style.call_args.args


@pytest.fixture
def unchanged_style():
    styles = build_styles([NOIR])
    returned = styles.service.update_style(NOIR.id, StyleChanges())
    return SimpleNamespace(returned=returned, repository=styles.repository)


@pytest.fixture
def renamed_onto_other_error():
    styles = build_styles([NOIR, ART])
    return capture(
        FilmConflictError, lambda: styles.service.update_style(NOIR.id, StyleChanges(name="art"))
    )


@pytest.fixture
def builtin_update_error():
    styles = build_styles([ANIME])
    return capture(
        FilmConflictError,
        lambda: styles.service.update_style(ANIME.id, StyleChanges(name="Anime 2")),
    )


@pytest.fixture
def unknown_style_error():
    styles = build_styles()
    return capture(
        StyleNotFoundError, lambda: styles.service.update_style("nope", StyleChanges(name="x"))
    )


@pytest.fixture(
    params=[
        ((1, 0), "Style 'Noir' is used by 1 project(s) and 0 character(s)"),
        ((0, 2), "Style 'Noir' is used by 0 project(s) and 2 character(s)"),
    ]
)
def used_style_outcome(request):
    usage, expected_message = request.param
    styles = build_styles([NOIR], usage)
    error = capture(FilmConflictError, lambda: styles.service.delete_style(NOIR.id))
    return SimpleNamespace(actual=str(error), expected=expected_message)


@pytest.fixture
def deleted_style_repository():
    styles = build_styles([NOIR])
    styles.service.delete_style(NOIR.id)
    return styles.repository


@pytest.fixture
def builtin_delete_error():
    styles = build_styles([ANIME])
    return capture(FilmConflictError, lambda: styles.service.delete_style(ANIME.id))


@pytest.fixture
def known_style():
    return get_known_style(build_styles([NOIR]).repository, NOIR.id)


@pytest.fixture
def unknown_known_style_error():
    repository = build_styles().repository
    return capture(InvalidFilmRequestError, lambda: get_known_style(repository, "no-such-style"))


def test_builtin_styles_are_the_thirteen_of_the_spec_in_order(written_builtin_styles):
    assert written_builtin_styles.names == [
        "Photorealistic",
        "3D Pixar",
        "Anime",
        "Felt & Wood Stop Motion",
        "Minecraft",
        "Oil Painting",
        "Studio Ghibli",
        "Watercolor",
        "Comic Book",
        "Cyberpunk",
        "Claymation",
        "LEGO",
        "Retro VHS",
    ]
    assert written_builtin_styles.ids == [
        "realistic",
        "3d_pixar",
        "anime",
        "stop_motion",
        "minecraft",
        "oil_painting",
        "ghibli",
        "watercolor",
        "comic_book",
        "cyberpunk",
        "claymation",
        "lego",
        "retro_vhs",
    ]


def test_builtin_styles_are_read_only_rows_with_flowkit_texts(written_builtin_styles):
    assert written_builtin_styles.builtin_flags == {True}
    assert written_builtin_styles.rows[0].lighting == "Studio lighting, highly detailed"
    assert written_builtin_styles.rows[0].style_instruction == (
        "Photorealistic RAW photograph, shot on Canon EOS R5, 35mm lens, "
        "natural available light, real footage."
    )
    assert written_builtin_styles.rows[2].negative_prompt == (
        "NOT photorealistic, NOT 3D render, NOT oil painting, "
        "NOT sketch, NOT watercolor, NOT Western cartoon."
    )
    assert written_builtin_styles.rows[12].scene_prefix == (
        "Retro VHS style, analog scan lines, warm washed-out colors, "
        "CRT curvature, nostalgic 80s grain."
    )


def test_list_puts_builtins_in_spec_order_then_custom_styles_as_found(listed_style_ids):
    assert listed_style_ids == ["realistic", "anime", "legacy", "art-1", "noir-1"]


def test_create_trims_texts_and_defaults_lighting(created_style):
    assert created_style.style.name == "Pastel"
    assert created_style.style.is_builtin is False
    assert created_style.style.style_instruction == "Soft pastel colors"
    assert created_style.style.negative_prompt is None
    assert created_style.style.scene_prefix == "Pastel scene"
    assert created_style.style.lighting == "Studio lighting, highly detailed"
    assert created_style.id_length == 36


def test_create_keeps_given_lighting(lit_style):
    assert lit_style.lighting == "Neon glow"


def test_create_rejects_invalid_texts(invalid_style_outcome):
    assert invalid_style_outcome.actual == invalid_style_outcome.expected


def test_create_rejects_a_name_taken_in_another_case(duplicate_style_error):
    assert str(duplicate_style_error) == "A style named 'noir' already exists"


def test_update_writes_every_sent_field_and_clears_blank_ones(updated_style):
    assert updated_style == (
        "noir-1",
        {
            "style_instruction": "Grainy noir",
            "negative_prompt": None,
            "scene_prefix": None,
            "lighting": "Studio lighting, highly detailed",
            "name": "NOIR",
        },
    )


def test_update_without_changes_writes_nothing(unchanged_style):
    assert unchanged_style.returned is NOIR
    assert unchanged_style.repository.update_style.called is False


def test_update_rejects_the_name_of_another_style(renamed_onto_other_error):
    assert str(renamed_onto_other_error) == "A style named 'art' already exists"


def test_update_refuses_a_builtin_style(builtin_update_error):
    assert str(builtin_update_error) == "Built-in styles cannot be changed"


def test_update_of_unknown_style_is_not_found(unknown_style_error):
    assert str(unknown_style_error) == "Style nope not found"


def test_delete_refuses_a_style_in_use(used_style_outcome):
    assert used_style_outcome.actual == used_style_outcome.expected


def test_delete_removes_an_unused_custom_style(deleted_style_repository):
    deleted_style_repository.delete_style.assert_called_once_with("noir-1")


def test_delete_refuses_a_builtin_style(builtin_delete_error):
    assert str(builtin_delete_error) == "Built-in styles cannot be changed"


def test_known_style_is_returned(known_style):
    assert known_style is NOIR


def test_unknown_style_is_a_bad_request(unknown_known_style_error):
    assert str(unknown_known_style_error) == "Style no-such-style not found"
