from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.common.captcha import CaptchaService
from app.modules.films.episode_router import router
from app.modules.films.episode_service import EpisodeDraft, EpisodeService
from app.modules.films.errors import (
    EpisodeActionNotAllowedError,
    EpisodeNotFoundError,
    EpisodeRunningError,
    FilmConflictError,
    FilmFileTooLargeError,
    InvalidFilmRequestError,
    PartNotFoundError,
)
from app.modules.films.film_access import EpisodeContext, FilmAccess, PartContext
from app.modules.films.http_errors import register_film_error_handlers
from app.modules.films.models import (
    Episode,
    EpisodePart,
    EpisodeSource,
    EpisodeStatus,
    EpisodeStep,
    FilmProject,
    MediaStatus,
    Scene,
    SubtitleStyle,
)
from app.modules.films.part_service import PartDraft, PartService
from app.modules.films.scene_service import SceneDraft, SceneService
from app.modules.films.stage_runner import EpisodeStageRunner
from app.modules.films.views import (
    EpisodeDetail,
    EpisodeSummary,
    PartCounts,
    PartDetail,
    PartSummary,
    ThumbnailCandidate,
)
from app.modules.media_generation.models import (
    GenerationKind,
    GenerationRequest,
    GenerationStatus,
)
from app.modules.prompt_presets.prompt_texts import DEFAULT_PRESET_PROMPTS
from app.modules.providers.provider_catalog import MediaKind

CREATED_AT = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)
CAPTCHA_HEADERS = {"X-Captcha-Token": "token-1"}
STOP_POINTS = {
    "afterOutline": True,
    "afterScript": True,
    "afterReferences": False,
    "afterSceneImages": True,
}
PROJECT = FilmProject(id="p1", name="Test Series", clip_duration_s=8)


def build_episode(**values) -> Episode:
    defaults = {
        "id": "e1",
        "project_id": "p1",
        "number": 1,
        "title": "Episode 1",
        "logline": None,
        "summary": None,
        "source": EpisodeSource.IDEA,
        "idea": "A storm",
        "source_job_id": None,
        "source_clone_id": None,
        "target_duration_s": 16,
        "stop_points": STOP_POINTS,
        "burn_subtitles": False,
        "subtitle_style": SubtitleStyle.CLEAN_WHITE,
        "music_prompt": None,
        "thumbnail_prompt": None,
        "music_status": MediaStatus.NONE,
        "music_path": None,
        "music_error": None,
        "preset": {"id": "preset-1", "name": "Default", "version": 3},
        "ai_used": {"writing_script": {"provider": "openai", "model": "gpt-6-luna"}},
        "film_outline_prompt": "OUTLINE PROMPT",
        "film_script_prompt": "SCRIPT PROMPT",
        "story_bible_prompt": "BIBLE PROMPT",
        "status": EpisodeStatus.DRAFT,
        "step": None,
        "error_message": None,
        "needs_assembly": False,
        "video_path": None,
        "subtitles_path": None,
        "thumbnail_path": None,
        "duration_ms": None,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
        "started_at": None,
        "finished_at": None,
    }
    return Episode(**{**defaults, **values})


def build_scene() -> Scene:
    return Scene(
        id="s1",
        episode_id="e1",
        part_id="pt1",
        position=0,
        image_prompt="Mai stands on the pier",
        video_prompt="0-3s: Mai walks.",
        narrator_text=None,
        character_ids=["c1"],
        clip_duration_s=12,
        image_status=MediaStatus.NONE,
        clip_status=MediaStatus.NONE,
        narration_status=MediaStatus.NONE,
        image_source=None,
        image_path=None,
        clip_path=None,
        narration_path=None,
        image_error=None,
        clip_error=None,
        narration_error=None,
        clip_duration_ms=None,
        narration_duration_ms=None,
        trim_start_ms=1000,
        trim_end_ms=None,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def build_request() -> GenerationRequest:
    return GenerationRequest(
        id="r1",
        kind=GenerationKind.SCENE_IMAGE,
        media_kind=MediaKind.IMAGE,
        project_id="p1",
        episode_id="e1",
        scene_id="s1",
        provider="google_flow",
        status=GenerationStatus.QUEUED,
        params={"aspect": "16:9"},
        attempts=0,
        created_at=CREATED_AT,
    )


def build_part() -> EpisodePart:
    return EpisodePart(
        id="pt1",
        episode_id="e1",
        position=0,
        title="The Dive",
        plan="Mai dives.",
        target_duration_s=60,
        recap="Mai reached the bell.",
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


PART_COUNTS = PartCounts(
    scene_count=4,
    images_done=3,
    clips_done=2,
    narration_done=1,
    narration_with_text=5,
    failed_count=6,
    open_request_count=7,
)


@pytest.fixture
def services():
    episode = build_episode()
    part = build_part()
    episodes = MagicMock(spec=EpisodeService)
    episodes.create_episode.return_value = EpisodeSummary(episode)
    episodes.update_episode.return_value = EpisodeSummary(episode)
    episodes.get_episode_detail.return_value = EpisodeDetail(
        summary=EpisodeSummary(build_episode(source=EpisodeSource.FILM_ANALYSIS)),
        project=PROJECT,
        parts=[PartSummary(part, PART_COUNTS)],
        open_requests=[build_request()],
        thumbnail_candidates=[ThumbnailCandidate(1, GenerationStatus.FAILED, None, "Blocked")],
        is_source_deleted=True,
    )
    parts = MagicMock(spec=PartService)
    parts.add_part.return_value = part
    parts.update_part.return_value = part
    parts.get_part_detail.return_value = PartDetail(
        part=part, scenes=[build_scene()], open_requests=[build_request()]
    )
    scenes = MagicMock(spec=SceneService)
    scenes.add_scene.return_value = build_scene()
    scenes.update_scene.return_value = build_scene()
    scenes.upload_image.return_value = build_scene()
    for method in ("generate_image", "generate_clip", "generate_narration", "edit_image"):
        getattr(scenes, method).return_value = build_request()
    stage_runner = MagicMock(spec=EpisodeStageRunner)
    running = build_episode(status=EpisodeStatus.RUNNING, step=EpisodeStep.WRITING_SCRIPT)
    for method in (
        "start",
        "continue_episode",
        "stop",
        "resume",
        "assemble",
        "rewrite_script",
        "rewrite_part",
    ):
        getattr(stage_runner, method).return_value = running
    access = MagicMock(spec=FilmAccess)
    access.get_episode.return_value = EpisodeContext(project=PROJECT, episode=episode)
    access.get_part.return_value = PartContext(project=PROJECT, episode=episode, part=part)
    captcha_service = MagicMock(spec=CaptchaService)
    captcha_service.verify.return_value = True
    return SimpleNamespace(
        episodes=episodes,
        parts=parts,
        scenes=scenes,
        stage_runner=stage_runner,
        access=access,
        captcha_service=captcha_service,
    )


@pytest.fixture
def client(services):
    app = FastAPI()
    app.include_router(router)
    register_film_error_handlers(app)
    app.state.container = SimpleNamespace(
        film_episode_service=services.episodes,
        film_part_service=services.parts,
        film_scene_service=services.scenes,
        film_stage_runner=services.stage_runner,
        film_access=services.access,
        captcha_service=services.captcha_service,
    )
    return TestClient(app)


@pytest.fixture
def created_response(client):
    return client.post(
        "/films/projects/p1/episodes",
        json={
            "source": "idea",
            "idea": "A storm",
            "targetDurationS": 16,
            "stopPoints": {"afterOutline": True, "afterScript": True, "afterReferences": False},
            "subtitleStyle": "cyber_amber",
            "presetId": "preset-1",
        },
        headers=CAPTCHA_HEADERS,
    )


def test_creating_an_episode_answers_201_with_the_episode(created_response):
    assert (created_response.status_code, created_response.json()["targetDurationS"]) == (201, 16)


def test_the_created_episode_uses_camel_case_stop_points(created_response):
    assert created_response.json()["stopPoints"] == STOP_POINTS


def test_the_creation_passes_the_body_as_a_draft(created_response, services):
    services.episodes.create_episode.assert_called_once_with(
        "p1",
        EpisodeDraft(
            source=EpisodeSource.IDEA,
            idea="A storm",
            source_job_id=None,
            source_clone_id=None,
            target_duration_s=16,
            stop_points=STOP_POINTS,
            burn_subtitles=False,
            subtitle_style=SubtitleStyle.CYBER_AMBER,
            preset_id="preset-1",
        ),
    )


@pytest.fixture
def rejected_captcha_response(client, services):
    services.captcha_service.verify.return_value = False
    return client.post(
        "/films/projects/p1/episodes", json={"source": "idea"}, headers={"X-Captcha-Token": ""}
    )


def test_creation_without_a_valid_captcha_is_refused(rejected_captcha_response):
    assert (rejected_captcha_response.status_code, rejected_captcha_response.json()) == (
        403,
        {"detail": "Captcha verification failed"},
    )


@pytest.fixture(
    params=[
        (InvalidFilmRequestError("Idea must be 1-5000 characters"), 400),
        (EpisodeNotFoundError("e9"), 404),
        (FilmConflictError("Job j1 is not done"), 409),
    ]
)
def failed_creation(request, client, services):
    error, status_code = request.param
    services.episodes.create_episode.side_effect = error
    response = client.post(
        "/films/projects/p1/episodes", json={"source": "idea"}, headers=CAPTCHA_HEADERS
    )
    return SimpleNamespace(
        actual=(response.status_code, response.json()),
        expected=(status_code, {"detail": str(error)}),
    )


def test_creation_errors_map_to_their_status(failed_creation):
    assert failed_creation.actual == failed_creation.expected


@pytest.fixture
def detail_response(client):
    return client.get("/films/episodes/e1")


def test_the_detail_holds_parts_requests_and_candidates_but_no_scenes(detail_response):
    body = detail_response.json()
    assert (
        detail_response.status_code,
        body["source"],
        body["projectName"],
        body["filmScriptPrompt"],
        body["aiUsed"],
        body["isSourceDeleted"],
        [part["id"] for part in body["parts"]],
        [request["id"] for request in body["openRequests"]],
        body["thumbnailCandidates"],
        "scenes" in body,
    ) == (
        200,
        "film_analysis",
        "Test Series",
        "SCRIPT PROMPT",
        {"writing_script": {"provider": "openai", "model": "gpt-6-luna", "label": "GPT-6 Luna"}},
        True,
        ["pt1"],
        ["r1"],
        [{"candidate": 1, "status": "failed", "path": None, "errorMessage": "Blocked"}],
        False,
    )


def test_each_part_of_the_detail_carries_its_counters_in_camel_case(detail_response):
    part = detail_response.json()["parts"][0]
    assert (
        part["episodeId"],
        part["position"],
        part["title"],
        part["plan"],
        part["targetDurationS"],
        part["recap"],
        part["sceneCount"],
        part["imagesDone"],
        part["clipsDone"],
        part["narrationDone"],
        part["narrationWithText"],
        part["failedCount"],
        part["openRequestCount"],
    ) == ("e1", 0, "The Dive", "Mai dives.", 60, "Mai reached the bell.", 4, 3, 2, 1, 5, 6, 7)


@pytest.fixture(
    params=[
        (
            {"film_outline_prompt": "OUTLINE PROMPT", "story_bible_prompt": "BIBLE PROMPT"},
            ("OUTLINE PROMPT", "BIBLE PROMPT"),
        ),
        (
            {"film_outline_prompt": None, "story_bible_prompt": None},
            (DEFAULT_PRESET_PROMPTS.film_outline, DEFAULT_PRESET_PROMPTS.story_bible),
        ),
    ]
)
def detail_prompts(request, client, services):
    episode_values, expected = request.param
    detail = services.episodes.get_episode_detail.return_value
    services.episodes.get_episode_detail.return_value = replace(
        detail, summary=EpisodeSummary(build_episode(**episode_values))
    )
    body = client.get("/films/episodes/e1").json()
    return SimpleNamespace(
        actual=(body["filmOutlinePrompt"], body["storyBiblePrompt"]), expected=expected
    )


def test_the_detail_shows_the_outline_and_bible_prompts_or_the_defaults(detail_prompts):
    assert detail_prompts.actual == detail_prompts.expected


@pytest.fixture
def patched_response(client):
    return client.patch(
        "/films/episodes/e1",
        json={"title": "New title", "musicPrompt": None, "stopPoints": {"afterScript": True}},
    )


def test_an_episode_edit_answers_the_episode(patched_response):
    assert (patched_response.status_code, patched_response.json()["id"]) == (200, "e1")


def test_an_episode_edit_passes_only_the_sent_fields(patched_response, services):
    services.episodes.update_episode.assert_called_once_with(
        "e1",
        {
            "title": "New title",
            "music_prompt": None,
            "stop_points": {
                "afterOutline": False,
                "afterScript": True,
                "afterReferences": False,
                "afterSceneImages": True,
            },
        },
    )


@pytest.fixture
def thumbnail_only_patch(client, services):
    client.patch("/films/episodes/e1", json={"thumbnailPrompt": "A bell in fog"})
    return services.episodes.update_episode.call_args.args


def test_an_edit_without_stop_points_passes_only_the_sent_field(thumbnail_only_patch):
    assert thumbnail_only_patch == ("e1", {"thumbnail_prompt": "A bell in fog"})


@pytest.fixture
def summary_patch(client, services):
    services.episodes.update_episode.return_value = EpisodeSummary(
        build_episode(summary="Mai finds the bell.")
    )
    response = client.patch("/films/episodes/e1", json={"summary": "Mai finds the bell."})
    return SimpleNamespace(response=response, call=services.episodes.update_episode.call_args)


def test_a_summary_edit_passes_the_summary(summary_patch):
    assert summary_patch.call.args == ("e1", {"summary": "Mai finds the bell."})


def test_a_summary_edit_answers_the_episode_with_its_summary(summary_patch):
    assert (summary_patch.response.status_code, summary_patch.response.json()["summary"]) == (
        200,
        "Mai finds the bell.",
    )


@pytest.fixture
def deleted_response(client):
    return client.delete("/films/episodes/e1")


def test_deleting_an_episode_answers_204(deleted_response, services):
    assert (deleted_response.status_code, services.episodes.delete_episode.call_args.args) == (
        204,
        ("e1",),
    )


@pytest.fixture(
    params=[
        ("start", "start"),
        ("continue", "continue_episode"),
        ("stop", "stop"),
        ("resume", "resume"),
        ("assemble", "assemble"),
        ("rewrite-script", "rewrite_script"),
    ]
)
def action_call(request, client, services):
    route, method = request.param
    response = client.post(f"/films/episodes/e1/{route}")
    return SimpleNamespace(
        response=response,
        calls=getattr(services.stage_runner, method).call_args_list,
        context=services.access.get_episode.return_value,
    )


def test_each_stage_action_answers_the_episode(action_call):
    assert (
        action_call.response.status_code,
        action_call.response.json()["status"],
        action_call.response.json()["step"],
    ) == (200, "running", "writing_script")


def test_each_stage_action_runs_on_the_episode_context(action_call):
    assert [call.args for call in action_call.calls] == [(action_call.context,)]


@pytest.fixture
def refused_action_response(client, services):
    services.stage_runner.continue_episode.side_effect = EpisodeActionNotAllowedError(
        "continue", 1, EpisodeStatus.DRAFT
    )
    return client.post("/films/episodes/e1/continue")


def test_a_refused_action_answers_409(refused_action_response):
    assert (refused_action_response.status_code, refused_action_response.json()) == (
        409,
        {"detail": "Cannot continue episode 1 while it is draft"},
    )


PART_BODY = {"title": "The Dive", "plan": "Mai dives.", "targetDurationS": 60}


@pytest.fixture
def added_part_response(client):
    return client.post("/films/episodes/e1/parts", json={"afterPosition": -1, **PART_BODY})


def test_adding_a_part_answers_201_with_the_part(added_part_response):
    body = added_part_response.json()
    assert (
        added_part_response.status_code,
        body["id"],
        body["episodeId"],
        body["position"],
        body["title"],
        body["plan"],
        body["targetDurationS"],
        body["recap"],
    ) == (201, "pt1", "e1", 0, "The Dive", "Mai dives.", 60, "Mai reached the bell.")


@pytest.fixture(params=[({"afterPosition": -1}, -1), ({"afterPosition": 2}, 2), ({}, None)])
def added_part_draft(request, client, services):
    position_values, after_position = request.param
    client.post("/films/episodes/e1/parts", json={**position_values, **PART_BODY})
    return SimpleNamespace(
        actual=services.parts.add_part.call_args.args,
        expected=(
            "e1",
            PartDraft(
                after_position=after_position,
                title="The Dive",
                plan="Mai dives.",
                target_duration_s=60,
            ),
        ),
    )


def test_adding_a_part_passes_the_body_as_a_draft(added_part_draft):
    assert added_part_draft.actual == added_part_draft.expected


@pytest.fixture
def part_detail_response(client, services):
    response = client.get("/films/parts/pt1")
    return SimpleNamespace(response=response, call=services.parts.get_part_detail.call_args)


def test_the_part_detail_holds_its_scenes_and_their_open_requests(part_detail_response):
    body = part_detail_response.response.json()
    assert (
        part_detail_response.response.status_code,
        part_detail_response.call.args,
        body["id"],
        body["targetDurationS"],
        [(scene["id"], scene["partId"]) for scene in body["scenes"]],
        [request["id"] for request in body["openRequests"]],
    ) == (200, ("pt1",), "pt1", 60, [("s1", "pt1")], ["r1"])


@pytest.fixture
def patched_part_response(client, services):
    response = client.patch(
        "/films/parts/pt1", json={"title": "The Deep", "targetDurationS": 90, "position": 2}
    )
    return SimpleNamespace(response=response, call=services.parts.update_part.call_args)


def test_a_part_edit_passes_only_the_sent_fields(patched_part_response):
    assert patched_part_response.call.args == (
        "pt1",
        {"title": "The Deep", "target_duration_s": 90, "position": 2},
    )


def test_a_part_edit_answers_the_part(patched_part_response):
    assert (
        patched_part_response.response.status_code,
        patched_part_response.response.json()["id"],
    ) == (200, "pt1")


@pytest.fixture
def deleted_part_response(client, services):
    response = client.delete("/films/parts/pt1")
    return SimpleNamespace(response=response, call=services.parts.delete_part.call_args)


def test_deleting_a_part_answers_204(deleted_part_response):
    assert (deleted_part_response.response.status_code, deleted_part_response.call.args) == (
        204,
        ("pt1",),
    )


@pytest.fixture
def rewritten_part_response(client, services):
    response = client.post("/films/parts/pt1/rewrite")
    return SimpleNamespace(
        response=response,
        access_calls=services.access.get_part.call_args_list,
        rewrite_calls=services.stage_runner.rewrite_part.call_args_list,
        context=services.access.get_part.return_value,
    )


def test_rewriting_a_part_answers_the_running_episode(rewritten_part_response):
    body = rewritten_part_response.response.json()
    assert (rewritten_part_response.response.status_code, body["status"], body["step"]) == (
        200,
        "running",
        "writing_script",
    )


def test_rewriting_a_part_runs_the_stage_runner_on_the_part_context(rewritten_part_response):
    assert (
        [call.args for call in rewritten_part_response.access_calls],
        [call.args for call in rewritten_part_response.rewrite_calls],
    ) == ([("pt1",)], [(rewritten_part_response.context,)])


@pytest.fixture(
    params=[
        (
            ("post", "/films/episodes/e1/parts", PART_BODY),
            ("parts", "add_part"),
            EpisodeRunningError(1),
            409,
        ),
        (
            ("get", "/films/parts/pt9", None),
            ("parts", "get_part_detail"),
            PartNotFoundError("pt9"),
            404,
        ),
        (
            ("patch", "/films/parts/pt1", {"position": 5}),
            ("parts", "update_part"),
            InvalidFilmRequestError("Position must be between 0 and 2"),
            400,
        ),
        (
            ("delete", "/films/parts/pt1", None),
            ("parts", "delete_part"),
            FilmConflictError("Part 1 has scenes — delete them first"),
            409,
        ),
        (
            ("post", "/films/parts/pt9/rewrite", None),
            ("access", "get_part"),
            PartNotFoundError("pt9"),
            404,
        ),
        (
            ("post", "/films/parts/pt1/rewrite", None),
            ("stage_runner", "rewrite_part"),
            FilmConflictError("Part 1 already has images or clips — delete them before rewriting"),
            409,
        ),
    ]
)
def failed_part_route(request, client, services):
    (method, path, body), (service_name, method_name), error, status_code = request.param
    getattr(getattr(services, service_name), method_name).side_effect = error
    response = client.request(method, path, json=body)
    return SimpleNamespace(
        actual=(response.status_code, response.json()),
        expected=(status_code, {"detail": str(error)}),
    )


def test_part_route_errors_map_to_their_status(failed_part_route):
    assert failed_part_route.actual == failed_part_route.expected


@pytest.fixture
def added_scene_response(client):
    return client.post(
        "/films/episodes/e1/scenes",
        json={
            "partId": "pt1",
            "afterPosition": -1,
            "imagePrompt": "Close-up of the bell",
            "videoPrompt": "0-3s: The bell sways.",
            "characterIds": ["c1"],
            "clipDurationS": 12,
        },
    )


def test_adding_a_scene_answers_201_with_the_scene(added_scene_response):
    assert (
        added_scene_response.status_code,
        added_scene_response.json()["partId"],
        added_scene_response.json()["trimStartMs"],
        added_scene_response.json()["clipDurationS"],
    ) == (201, "pt1", 1000, 12)


def test_adding_a_scene_passes_a_draft(added_scene_response, services):
    services.scenes.add_scene.assert_called_once_with(
        "e1",
        SceneDraft(
            part_id="pt1",
            after_position=-1,
            image_prompt="Close-up of the bell",
            video_prompt="0-3s: The bell sways.",
            narrator_text=None,
            character_ids=["c1"],
            clip_duration_s=12,
        ),
    )


@pytest.fixture
def partless_scene_response(client, services):
    response = client.post(
        "/films/episodes/e1/scenes",
        json={"imagePrompt": "Close-up of the bell", "videoPrompt": "0-3s: The bell sways."},
    )
    return SimpleNamespace(response=response, is_called=services.scenes.add_scene.called)


def test_adding_a_scene_without_a_part_is_refused(partless_scene_response):
    assert (
        partless_scene_response.response.status_code,
        partless_scene_response.response.json()["detail"][0]["loc"],
        partless_scene_response.is_called,
    ) == (422, ["body", "partId"], False)


@pytest.fixture
def patched_scene_response(client):
    return client.patch(
        "/films/scenes/s1",
        json={"narratorText": None, "trimEndMs": None, "position": 2, "clipDurationS": 20},
    )


def test_a_scene_edit_passes_explicit_nulls(patched_scene_response, services):
    services.scenes.update_scene.assert_called_once_with(
        "s1", {"narrator_text": None, "trim_end_ms": None, "position": 2, "clip_duration_s": 20}
    )


def test_a_scene_edit_answers_the_scene(patched_scene_response):
    assert (patched_scene_response.status_code, patched_scene_response.json()["id"]) == (
        200,
        "s1",
    )


@pytest.fixture
def deleted_scene_response(client):
    return client.delete("/films/scenes/s1")


def test_deleting_a_scene_answers_204(deleted_scene_response, services):
    assert (deleted_scene_response.status_code, services.scenes.delete_scene.call_args.args) == (
        204,
        ("s1",),
    )


@pytest.fixture
def uploaded_image_response(client, services):
    response = client.post(
        "/films/scenes/s1/image", files={"file": ("IMG-L.png", b"image", "image/png")}
    )
    upload = services.scenes.upload_image.call_args.args[1]
    return SimpleNamespace(response=response, filename=upload.filename)


def test_uploading_a_scene_image_answers_the_scene(uploaded_image_response):
    assert (
        uploaded_image_response.response.status_code,
        uploaded_image_response.filename,
    ) == (200, "IMG-L.png")


@pytest.fixture
def too_large_upload_response(client, services):
    services.scenes.upload_image.side_effect = FilmFileTooLargeError("Image exceeds 20 MB")
    return client.post(
        "/films/scenes/s1/image", files={"file": ("IMG-L.png", b"image", "image/png")}
    )


def test_a_too_large_image_answers_413(too_large_upload_response):
    assert (too_large_upload_response.status_code, too_large_upload_response.json()) == (
        413,
        {"detail": "Image exceeds 20 MB"},
    )


@pytest.fixture(params=["generate-image", "generate-clip", "generate-narration"])
def generation_response(request, client):
    return client.post(f"/films/scenes/s1/{request.param}")


def test_a_generation_answers_202_with_its_request(generation_response):
    assert (
        generation_response.status_code,
        generation_response.json()["id"],
        generation_response.json()["kind"],
    ) == (202, "r1", "scene_image")


@pytest.fixture
def edit_image_response(client):
    return client.post("/films/scenes/s1/edit-image", json={"prompt": "Make it night"})


def test_an_image_edit_answers_202_with_its_prompt_passed(edit_image_response, services):
    assert (edit_image_response.status_code, services.scenes.edit_image.call_args.args) == (
        202,
        ("s1", "Make it night"),
    )


@pytest.fixture
def busy_scene_response(client, services):
    services.scenes.generate_image.side_effect = FilmConflictError("Scene 1 has generation running")
    return client.post("/films/scenes/s1/generate-image")


def test_a_busy_scene_answers_409(busy_scene_response):
    assert (busy_scene_response.status_code, busy_scene_response.json()) == (
        409,
        {"detail": "Scene 1 has generation running"},
    )
