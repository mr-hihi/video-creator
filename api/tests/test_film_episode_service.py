from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, call

import pytest

from app.modules.ai_models.ai_calls import AiProviderNotSetUpError, AiStepGroup
from app.modules.ai_models.step_models import AiStepModels
from app.modules.film_clones.clone_files import CloneFiles
from app.modules.film_clones.models import (
    AssetKind,
    CloneAspect,
    CloneAsset,
    CloneImageStatus,
    CloneScene,
    CloneStatus,
    CloneStep,
    FilmClone,
)
from app.modules.film_clones.repository import FilmCloneRepository
from app.modules.films.analysis_source import AnalysisSource, AnalysisSourceTools
from app.modules.films.clone_source import CloneSource, CloneSourceTools
from app.modules.films.episode_service import EpisodeDraft, EpisodeService, EpisodeServiceTools
from app.modules.films.errors import (
    EpisodeRunningError,
    FilmConflictError,
    FilmNotFoundError,
    InvalidFilmRequestError,
)
from app.modules.films.film_access import FilmAccess
from app.modules.films.film_files import FilmFiles
from app.modules.films.film_imports import FilmImports
from app.modules.films.models import (
    EntityType,
    Episode,
    EpisodePart,
    EpisodeSource,
    EpisodeStatus,
    FilmLanguage,
    FilmProject,
    MediaStatus,
    Orientation,
    ProjectStatus,
    ReferenceSource,
    Scene,
    SceneImageSource,
    Style,
    SubtitleStyle,
)
from app.modules.films.repository import FilmRepository
from app.modules.films.views import PartCounts, PartSummary, ThumbnailCandidate
from app.modules.jobs.models import Job, JobOutputKind, JobStatus, JobType
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.storage import JobStorage
from app.modules.media_generation.models import (
    GenerationKind,
    GenerationRequest,
    GenerationStatus,
)
from app.modules.prompt_presets.errors import PromptPresetNotFoundError
from app.modules.prompt_presets.prompt_texts import DEFAULT_PRESET_PROMPTS
from app.modules.prompt_presets.service import PresetSnapshot, PromptPresetService

UPLOAD_MAX_MB = 20
STOP_POINTS = {"afterScript": True, "afterReferences": False, "afterSceneImages": True}
STYLE = Style(
    id="realistic",
    name="Photorealistic",
    is_builtin=True,
    style_instruction="Photorealistic photo.",
    negative_prompt=None,
    scene_prefix=None,
    lighting="Studio lighting",
)
SNAPSHOT = PresetSnapshot(
    preset_id="preset-1",
    name="Default",
    version=3,
    prompts=replace(
        DEFAULT_PRESET_PROMPTS,
        film_outline="OUTLINE PROMPT",
        film_script="SCRIPT PROMPT",
        story_bible="BIBLE PROMPT",
    ),
)
ANALYSIS_OUTPUTS = {
    JobOutputKind.VIDEO_NOTES: "# Notes",
    JobOutputKind.CHARACTER_IMAGE_PROMPTS: "## Mai\nRed coat",
    JobOutputKind.CHARACTER_VOICE_PROMPTS: "## Mai\nSoft",
    JobOutputKind.SCENE_PROMPTS: "## Scene 1\nFog",
}


@dataclass(frozen=True)
class Outcome:
    actual: Any
    expected: Any


def build_project(**values) -> FilmProject:
    defaults = {
        "id": "p1",
        "name": "Test Series",
        "language": FilmLanguage.ENGLISH,
        "orientation": Orientation.LANDSCAPE,
        "style_id": "realistic",
        "clip_duration_s": 8,
        "status": ProjectStatus.ACTIVE,
        "last_episode_number": 2,
    }
    return FilmProject(**{**defaults, **values})


def build_draft(**values) -> EpisodeDraft:
    defaults = {
        "source": EpisodeSource.IDEA,
        "idea": " A storm ",
        "source_job_id": None,
        "source_clone_id": None,
        "target_duration_s": 16,
        "stop_points": STOP_POINTS,
        "burn_subtitles": False,
        "subtitle_style": SubtitleStyle.CLEAN_WHITE,
        "preset_id": None,
    }
    return EpisodeDraft(**{**defaults, **values})


def build_episode(**values) -> Episode:
    defaults = {
        "id": "e2",
        "project_id": "p1",
        "number": 2,
        "title": "Episode 2",
        "source": EpisodeSource.IDEA,
        "idea": "A storm",
        "source_job_id": None,
        "source_clone_id": None,
        "target_duration_s": 16,
        "stop_points": STOP_POINTS,
        "burn_subtitles": False,
        "subtitle_style": SubtitleStyle.CLEAN_WHITE,
        "music_prompt": "Soft piano",
        "music_status": MediaStatus.NONE,
        "music_path": None,
        "thumbnail_prompt": None,
        "status": EpisodeStatus.DRAFT,
        "film_script_prompt": "SCRIPT PROMPT",
    }
    return Episode(**{**defaults, **values})


def build_job(job_id: str, job_type: JobType, status: JobStatus = JobStatus.DONE) -> Job:
    return Job(id=job_id, type=job_type, status=status, source_filename="film.mp4", options={})


def build_clone(clone_id: str, **values) -> FilmClone:
    defaults = {
        "id": clone_id,
        "job_id": "job-k",
        "status": CloneStatus.DONE,
        "step": CloneStep.GENERATING_SCENE_IMAGES,
        "script_language": "ja",
        "aspect": CloneAspect.LANDSCAPE,
    }
    return FilmClone(**{**defaults, **values})


def build_asset(asset_id: str, kind: AssetKind, name: str, **values) -> CloneAsset:
    defaults = {
        "id": asset_id,
        "clone_id": "k2",
        "kind": kind,
        "name": name,
        "description": f"{name} original",
        "changed": False,
        "localized_name": None,
        "localized_description": None,
        "reference_frame": None,
        "reference_status": CloneImageStatus.NONE,
        "reference_path": None,
    }
    return CloneAsset(**{**defaults, **values})


def build_clone_scene(scene_id: str, position: int, **values) -> CloneScene:
    defaults = {
        "id": scene_id,
        "clone_id": "k2",
        "shot_id": f"shot-{scene_id}",
        "position": position,
        "description": "Something happens.",
        "dialogue": None,
        "image_prompt": f"{scene_id} prompt",
        "asset_ids": [],
        "image_status": CloneImageStatus.DONE,
        "image_path": None,
    }
    return CloneScene(**{**defaults, **values})


def build_request(request_id: str, candidate: int, status: GenerationStatus, **values):
    defaults = {
        "id": request_id,
        "kind": GenerationKind.THUMBNAIL,
        "episode_id": "e2",
        "params": {"candidate": candidate},
        "status": status,
        "output_path": None,
        "error_message": None,
    }
    return GenerationRequest(**{**defaults, **values})


def write_file(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def build_parts(tmp_path, project: FilmProject | None = None):
    project = project or build_project()
    repository = MagicMock(spec=FilmRepository)
    repository.find_project.return_value = project
    repository.find_style.return_value = STYLE
    repository.find_character_by_name.return_value = None
    repository.find_open_requests_for_episode.return_value = []

    def add_episode(creation):
        creation.episode.number = project.last_episode_number + 1
        return creation.episode

    repository.add_episode.side_effect = add_episode
    files = FilmFiles(tmp_path, UPLOAD_MAX_MB)
    imports = FilmImports(files)
    job_repository = MagicMock(spec=JobRepository)
    job_repository.find_by_id.return_value = None
    job_storage = JobStorage(tmp_path / "jobs", 1)
    clone_repository = MagicMock(spec=FilmCloneRepository)
    clone_repository.find_by_id.return_value = None
    clone_files = CloneFiles(tmp_path)
    preset_service = MagicMock(spec=PromptPresetService)
    preset_service.get_job_snapshot.return_value = SNAPSHOT
    step_models = MagicMock(spec=AiStepModels)
    service = EpisodeService(
        EpisodeServiceTools(
            repository=repository,
            access=FilmAccess(repository),
            files=files,
            imports=imports,
            preset_service=preset_service,
            step_models=step_models,
            analysis_source=AnalysisSource(AnalysisSourceTools(files, job_repository, job_storage)),
            clone_source=CloneSource(
                CloneSourceTools(
                    repository=repository,
                    files=files,
                    imports=imports,
                    clone_repository=clone_repository,
                    clone_files=clone_files,
                    job_storage=job_storage,
                )
            ),
        )
    )
    return SimpleNamespace(
        service=service,
        project=project,
        repository=repository,
        files=files,
        job_repository=job_repository,
        job_storage=job_storage,
        clone_repository=clone_repository,
        clone_files=clone_files,
        preset_service=preset_service,
        step_models=step_models,
    )


def added_creation(parts):
    return parts.repository.add_episode.call_args.args[0]


@pytest.fixture
def idea_creation(tmp_path):
    parts = build_parts(tmp_path)
    summary = parts.service.create_episode("p1", build_draft())
    return SimpleNamespace(summary=summary, creation=added_creation(parts), parts=parts)


def test_an_idea_episode_is_created_as_a_draft_with_the_next_number(idea_creation):
    episode = idea_creation.creation.episode
    assert (
        episode.project_id,
        episode.number,
        episode.title,
        episode.source,
        episode.idea,
        episode.source_job_id,
        episode.source_clone_id,
        episode.target_duration_s,
        episode.stop_points,
        episode.status,
        episode.step,
        episode.needs_assembly,
        episode.music_status,
    ) == (
        "p1",
        3,
        "Episode 3",
        EpisodeSource.IDEA,
        "A storm",
        None,
        None,
        16,
        STOP_POINTS,
        EpisodeStatus.DRAFT,
        None,
        False,
        MediaStatus.NONE,
    )


def test_the_episode_copies_the_preset_and_its_three_writing_prompts(idea_creation):
    episode = idea_creation.creation.episode
    assert (
        episode.preset,
        episode.film_outline_prompt,
        episode.film_script_prompt,
        episode.story_bible_prompt,
    ) == (
        {"id": "preset-1", "name": "Default", "version": 3},
        "OUTLINE PROMPT",
        "SCRIPT PROMPT",
        "BIBLE PROMPT",
    )


def test_the_episode_checks_the_film_script_model(idea_creation):
    idea_creation.parts.step_models.ensure_set_up.assert_called_once_with(
        (AiStepGroup.FILM_SCRIPT,)
    )


@pytest.fixture
def openai_without_key_creation(tmp_path):
    parts = build_parts(tmp_path, build_project(**JAPANESE))
    parts.clone_repository.find_by_id.side_effect = CLONES.get
    parts.step_models.ensure_set_up.side_effect = AiProviderNotSetUpError("OpenAI")
    with pytest.raises(AiProviderNotSetUpError) as error:
        parts.service.create_episode(
            "p1", build_draft(source=CLONE, source_clone_id="k-9", idea=None)
        )
    return SimpleNamespace(message=str(error.value), parts=parts)


def test_a_provider_without_a_key_is_refused_before_the_clone_checks(
    openai_without_key_creation,
):
    assert openai_without_key_creation.message == "OpenAI is not set up — open Settings"
    openai_without_key_creation.parts.repository.add_episode.assert_not_called()


def test_an_idea_episode_adds_no_character_part_or_scene(idea_creation):
    creation = idea_creation.creation
    assert (
        creation.new_characters,
        creation.linked_character_ids,
        creation.parts,
        creation.scenes,
    ) == ((), (), (), ())


def test_the_summary_holds_the_episode_with_its_target(idea_creation):
    assert idea_creation.summary.episode.target_duration_s == 16


def test_the_default_preset_is_used_without_a_preset_id(idea_creation):
    idea_creation.parts.preset_service.get_job_snapshot.assert_called_once_with(None)


def test_a_matching_default_title_is_not_rewritten(idea_creation):
    assert not idea_creation.parts.repository.update_episode.called


JOBS = {
    "fa-1": build_job("fa-1", JobType.FILM_ANALYSIS),
    "job-v": build_job("job-v", JobType.VIDEO_TO_MARKDOWN),
    "fa-2": build_job("fa-2", JobType.FILM_ANALYSIS, JobStatus.PROCESSING),
}
CLONES = {
    "k1": build_clone("k1", status=CloneStatus.RUNNING),
    "k2": build_clone("k2"),
}
ANALYSIS = EpisodeSource.FILM_ANALYSIS
CLONE = EpisodeSource.FILM_CLONE
JAPANESE = {"language": FilmLanguage.JAPANESE}
IDEA_MESSAGE = "Idea must be 1-5000 characters"
TARGET_MESSAGE = "Target duration must be at least 8 seconds"
SUMMARY_MESSAGE = "Summary must be at most 10000 characters"


@pytest.fixture(
    params=[
        ({"idea": "   "}, {}, InvalidFilmRequestError, IDEA_MESSAGE),
        ({"idea": None}, {}, InvalidFilmRequestError, IDEA_MESSAGE),
        (
            {"source": ANALYSIS, "idea": "x" * 5001, "source_job_id": "fa-1"},
            {},
            InvalidFilmRequestError,
            IDEA_MESSAGE,
        ),
        ({"target_duration_s": 7}, {}, InvalidFilmRequestError, TARGET_MESSAGE),
        (
            {"source": ANALYSIS},
            {},
            InvalidFilmRequestError,
            "sourceJobId is required for a film analysis source",
        ),
        (
            {"source": ANALYSIS, "source_job_id": "job-v"},
            {},
            FilmConflictError,
            "Job job-v is not a film analysis",
        ),
        (
            {"source": ANALYSIS, "source_job_id": "fa-2"},
            {},
            FilmConflictError,
            "Job fa-2 is not done",
        ),
        (
            {"source": ANALYSIS, "source_job_id": "fa-9"},
            {},
            FilmNotFoundError,
            "Job fa-9 not found",
        ),
        (
            {"preset_id": "missing"},
            {},
            InvalidFilmRequestError,
            "Prompt preset missing not found",
        ),
        ({}, None, FilmNotFoundError, "Film project p1 not found"),
        (
            {},
            {"status": ProjectStatus.ARCHIVED},
            FilmConflictError,
            "Film project p1 is archived",
        ),
        (
            {"source": CLONE},
            JAPANESE,
            InvalidFilmRequestError,
            "sourceCloneId is required for a film clone source",
        ),
        (
            {"source": CLONE, "source_clone_id": "k-9"},
            JAPANESE,
            FilmNotFoundError,
            "Film clone k-9 not found",
        ),
        (
            {"source": CLONE, "source_clone_id": "k1"},
            JAPANESE,
            FilmConflictError,
            "Film clone k1 is not done",
        ),
        (
            {"source": CLONE, "source_clone_id": "k2"},
            {},
            FilmConflictError,
            "The clone is written in ja; the project narrates in en",
        ),
        (
            {"source": CLONE, "source_clone_id": "k2"},
            {**JAPANESE, "orientation": Orientation.PORTRAIT},
            FilmConflictError,
            "The clone's images are 16:9; the project is portrait",
        ),
    ]
)
def rejected_creation(request, tmp_path):
    draft_values, project_values, error_class, message = request.param
    parts = build_parts(tmp_path, build_project(**(project_values or {})))
    if project_values is None:
        parts.repository.find_project.return_value = None
    parts.job_repository.find_by_id.side_effect = JOBS.get
    parts.clone_repository.find_by_id.side_effect = CLONES.get
    parts.preset_service.get_job_snapshot.side_effect = lambda preset_id: (
        _raise(PromptPresetNotFoundError(preset_id)) if preset_id else SNAPSHOT
    )
    with pytest.raises(error_class) as error:
        parts.service.create_episode("p1", build_draft(**draft_values))
    return Outcome(
        actual=(str(error.value), parts.repository.add_episode.called),
        expected=(message, False),
    )


def _raise(error: Exception):
    raise error


def test_an_invalid_creation_is_refused_and_adds_nothing(rejected_creation):
    assert rejected_creation.actual == rejected_creation.expected


@pytest.fixture(params=[8, 3600])
def accepted_target_creation(request, tmp_path):
    parts = build_parts(tmp_path, build_project(clip_duration_s=4))
    summary = parts.service.create_episode("p1", build_draft(target_duration_s=request.param))
    return Outcome(summary.episode.target_duration_s, request.param)


def test_a_target_of_at_least_8_seconds_has_no_upper_limit(accepted_target_creation):
    assert accepted_target_creation.actual == accepted_target_creation.expected


@pytest.fixture
def analysis_creation(tmp_path):
    parts = build_parts(tmp_path)
    parts.job_repository.find_by_id.side_effect = JOBS.get
    parts.job_repository.find_outputs.return_value = ANALYSIS_OUTPUTS
    write_file(parts.job_storage.images_dir("fa-1") / "moment-01.jpg", b"m1")
    write_file(parts.job_storage.images_dir("fa-1") / "scene-02.jpg", b"s2")
    parts.service.create_episode(
        "p1", build_draft(source=ANALYSIS, source_job_id="fa-1", idea="", target_duration_s=16)
    )
    episode = added_creation(parts).episode
    source_dir = parts.files.source_dir("p1", episode.id)
    return SimpleNamespace(episode=episode, source_dir=source_dir, parts=parts)


def test_an_analysis_episode_keeps_its_job_and_no_idea(analysis_creation):
    assert (analysis_creation.episode.source_job_id, analysis_creation.episode.idea) == (
        "fa-1",
        None,
    )


def test_the_analysis_prompts_and_frames_are_copied(analysis_creation):
    assert sorted(path.name for path in analysis_creation.source_dir.iterdir()) == [
        "character_image_prompts.md",
        "character_voice_prompts.md",
        "images",
        "scene_prompts.md",
    ]


def test_the_copied_prompt_files_equal_the_job_outputs(analysis_creation):
    source_dir = analysis_creation.source_dir
    assert [
        (source_dir / name).read_text(encoding="utf-8")
        for name in ("character_image_prompts.md", "character_voice_prompts.md", "scene_prompts.md")
    ] == ["## Mai\nRed coat", "## Mai\nSoft", "## Scene 1\nFog"]


def test_every_frame_of_the_job_is_copied(analysis_creation):
    assert sorted(path.name for path in (analysis_creation.source_dir / "images").iterdir()) == [
        "moment-01.jpg",
        "scene-02.jpg",
    ]


@pytest.fixture
def frameless_analysis_dir(tmp_path):
    parts = build_parts(tmp_path)
    parts.job_repository.find_by_id.return_value = build_job("fa-3", JobType.FILM_ANALYSIS_RERUN)
    parts.job_repository.find_outputs.return_value = {}
    parts.service.create_episode(
        "p1", build_draft(source=ANALYSIS, source_job_id="fa-3", idea="Set it in winter")
    )
    return parts.files.source_dir("p1", added_creation(parts).episode.id)


def test_a_job_without_frames_or_outputs_gives_empty_prompt_files(frameless_analysis_dir):
    assert sorted(
        (path.name, path.read_text(encoding="utf-8")) for path in frameless_analysis_dir.iterdir()
    ) == [
        ("character_image_prompts.md", ""),
        ("character_voice_prompts.md", ""),
        ("scene_prompts.md", ""),
    ]


@pytest.fixture
def failed_analysis_creation(tmp_path):
    parts = build_parts(tmp_path)
    parts.job_repository.find_by_id.side_effect = JOBS.get
    parts.job_repository.find_outputs.return_value = ANALYSIS_OUTPUTS
    parts.repository.add_episode.side_effect = RuntimeError("database gone")
    with pytest.raises(RuntimeError) as error:
        parts.service.create_episode("p1", build_draft(source=ANALYSIS, source_job_id="fa-1"))
    episode = parts.repository.add_episode.call_args.args[0].episode
    return SimpleNamespace(error=error.value, episode_dir=parts.files.episode_dir("p1", episode.id))


def test_a_failed_analysis_creation_raises(failed_analysis_creation):
    assert str(failed_analysis_creation.error) == "database gone"


def test_a_failed_analysis_creation_removes_the_copies(failed_analysis_creation):
    assert not failed_analysis_creation.episode_dir.exists()


def build_clone_parts(tmp_path):
    parts = build_parts(tmp_path, build_project(language=FilmLanguage.JAPANESE, clip_duration_s=6))
    parts.clone_repository.find_by_id.side_effect = CLONES.get
    kyoto = SimpleNamespace(id="lib-kyoto", name="Kyoto Temple")
    parts.repository.find_character_by_name.side_effect = lambda name: (
        kyoto if name.casefold() == "kyoto temple" else None
    )
    write_file(parts.clone_files.to_absolute("k2/references/a2.png"), b"mai-ref")
    write_file(parts.job_storage.output_dir("job-k") / "images" / "frame-03.jpg", b"fan-frame")
    write_file(parts.clone_files.to_absolute("k2/scenes/cs1.png"), b"scene-1")
    write_file(parts.clone_files.to_absolute("k2/scenes/cs2.webp"), b"scene-2")
    parts.clone_repository.find_assets.return_value = [
        build_asset(
            "a1",
            AssetKind.LOCATION,
            "Palace",
            changed=True,
            localized_name="Kyoto Temple",
            localized_description="A temple",
            reference_status=CloneImageStatus.DONE,
            reference_path="k2/references/a1.png",
        ),
        build_asset(
            "a2",
            AssetKind.CHARACTER,
            "Min",
            changed=True,
            localized_name="Mai",
            localized_description="A Kyoto girl",
            reference_status=CloneImageStatus.DONE,
            reference_path="k2/references/a2.png",
        ),
        build_asset(
            "a3",
            AssetKind.PROP,
            "Fan",
            description="A paper fan",
            reference_frame="images/frame-03.jpg",
        ),
        build_asset("a4", AssetKind.CHARACTER, "Crowd"),
        build_asset(
            "a5",
            AssetKind.CHARACTER,
            "Ghost",
            changed=True,
            localized_name="Ghost",
            localized_description="A pale ghost",
            reference_status=CloneImageStatus.FAILED,
        ),
        build_asset("a6", AssetKind.COSTUME, "MAI"),
    ]
    parts.clone_repository.find_scenes.return_value = [
        build_clone_scene(
            "cs1",
            0,
            description="She bows.",
            dialogue="Mai: Okaeri.",
            image_prompt="Mai bows at the gate",
            asset_ids=["a2", "a3", "a6"],
            image_path="k2/scenes/cs1.png",
        ),
        build_clone_scene(
            "cs2",
            1,
            description="The crowd cheers.",
            asset_ids=["a4", "unknown"],
            image_path="k2/scenes/cs2.webp",
        ),
        build_clone_scene(
            "cs3",
            2,
            description="Night falls.",
            dialogue="  ",
            image_status=CloneImageStatus.FAILED,
        ),
    ]
    return parts


@pytest.fixture
def clone_creation(tmp_path):
    parts = build_clone_parts(tmp_path)
    parts.service.create_episode(
        "p1", build_draft(source=CLONE, source_clone_id="k2", target_duration_s=5, idea=None)
    )
    creation = added_creation(parts)
    characters_by_name = {character.name: character for character in creation.new_characters}
    return SimpleNamespace(
        creation=creation,
        mai=characters_by_name["Mai"],
        fan=characters_by_name["Fan"],
        crowd=characters_by_name["Crowd"],
        ghost=characters_by_name["Ghost"],
        parts=parts,
    )


def test_a_clone_episode_lasts_its_scenes_times_the_kept_clip(clone_creation):
    episode = clone_creation.creation.episode
    assert (episode.target_duration_s, episode.source_clone_id, episode.source_job_id) == (
        15,
        "k2",
        None,
    )


def test_every_asset_becomes_a_linked_character(clone_creation):
    assert clone_creation.creation.linked_character_ids == (
        "lib-kyoto",
        clone_creation.mai.id,
        clone_creation.fan.id,
        clone_creation.crowd.id,
        clone_creation.ghost.id,
    )


def test_new_characters_take_the_type_of_their_asset_kind(clone_creation):
    assert [
        (character.name, character.entity_type, character.description)
        for character in clone_creation.creation.new_characters
    ] == [
        ("Mai", EntityType.CHARACTER, "A Kyoto girl"),
        ("Fan", EntityType.VISUAL_ASSET, "A paper fan"),
        ("Crowd", EntityType.CHARACTER, "Crowd original"),
        ("Ghost", EntityType.CHARACTER, "A pale ghost"),
    ]


def test_a_changed_asset_copies_its_generated_reference(clone_creation):
    mai = clone_creation.mai
    assert (
        mai.reference_status,
        mai.reference_source,
        mai.reference_path,
        mai.origin_clone_id,
        mai.style_id,
        clone_creation.parts.files.to_absolute(mai.reference_path).read_bytes(),
    ) == (
        MediaStatus.DONE,
        ReferenceSource.FILM_CLONE,
        f"characters/{mai.id}/reference.png",
        "k2",
        "realistic",
        b"mai-ref",
    )


def test_an_unchanged_asset_copies_its_reference_frame(clone_creation):
    fan = clone_creation.fan
    assert (
        fan.reference_path,
        clone_creation.parts.files.to_absolute(fan.reference_path).read_bytes(),
    ) == (f"characters/{fan.id}/reference.jpg", b"fan-frame")


def test_assets_without_a_usable_reference_stay_none(clone_creation):
    assert (clone_creation.crowd.reference_status, clone_creation.ghost.reference_status) == (
        MediaStatus.NONE,
        MediaStatus.NONE,
    )


def test_a_library_character_is_linked_as_it_is(clone_creation):
    assert not clone_creation.parts.repository.update_character.called


def test_clone_scenes_become_scenes_at_the_same_positions(clone_creation):
    assert [
        (
            scene.position,
            scene.image_prompt,
            scene.video_prompt,
            scene.narrator_text,
            scene.character_ids,
            scene.image_status,
            scene.image_source,
            scene.trim_start_ms,
        )
        for scene in clone_creation.creation.scenes
    ] == [
        (
            0,
            "Mai bows at the gate",
            "She bows.\nDialogue: Mai: Okaeri.",
            None,
            [clone_creation.mai.id, clone_creation.fan.id],
            MediaStatus.DONE,
            SceneImageSource.FILM_CLONE,
            1000,
        ),
        (
            1,
            "cs2 prompt",
            "The crowd cheers.",
            None,
            [clone_creation.crowd.id],
            MediaStatus.DONE,
            SceneImageSource.FILM_CLONE,
            1000,
        ),
        (2, "cs3 prompt", "Night falls.", None, [], MediaStatus.NONE, None, 1000),
    ]


def test_clone_scenes_take_the_project_clip_length(clone_creation):
    assert [scene.clip_duration_s for scene in clone_creation.creation.scenes] == [6, 6, 6]


def test_clone_scene_images_are_copied(clone_creation):
    files = clone_creation.parts.files
    assert [
        files.to_absolute(scene.image_path).read_bytes()
        for scene in clone_creation.creation.scenes[:2]
    ] == [b"scene-1", b"scene-2"]


def test_clone_scenes_fill_one_part_named_after_their_range(clone_creation):
    creation = clone_creation.creation
    assert [
        (part.episode_id, part.position, part.title, part.plan, part.target_duration_s, part.recap)
        for part in creation.parts
    ] == [(creation.episode.id, 0, "Part 1", "Scenes 1-3 of the film clone.", 15, None)]


def test_every_clone_scene_belongs_to_the_part(clone_creation):
    creation = clone_creation.creation
    assert [scene.part_id for scene in creation.scenes] == [
        creation.parts[0].id,
        creation.parts[0].id,
        creation.parts[0].id,
    ]


LONG_CLONE_SCENE_COUNT = 170


@pytest.fixture
def long_clone_creation(tmp_path):
    parts = build_parts(tmp_path, build_project(**JAPANESE))
    parts.clone_repository.find_by_id.side_effect = CLONES.get
    parts.clone_repository.find_assets.return_value = []
    parts.clone_repository.find_scenes.return_value = [
        build_clone_scene(f"cs{index}", index) for index in range(LONG_CLONE_SCENE_COUNT)
    ]
    parts.service.create_episode("p1", build_draft(source=CLONE, source_clone_id="k2", idea=None))
    creation = added_creation(parts)
    return SimpleNamespace(
        creation=creation,
        positions_by_part=[
            [scene.position for scene in creation.scenes if scene.part_id == part.id]
            for part in creation.parts
        ],
    )


def test_a_long_clone_fills_parts_of_80_scenes(long_clone_creation):
    assert [
        (part.position, part.title, part.plan, part.target_duration_s, part.recap)
        for part in long_clone_creation.creation.parts
    ] == [
        (0, "Part 1", "Scenes 1-80 of the film clone.", 560, None),
        (1, "Part 2", "Scenes 81-160 of the film clone.", 560, None),
        (2, "Part 3", "Scenes 161-170 of the film clone.", 70, None),
    ]


def test_a_long_clone_numbers_scene_positions_within_each_part(long_clone_creation):
    assert long_clone_creation.positions_by_part == [
        list(range(80)),
        list(range(80)),
        list(range(10)),
    ]


def test_a_long_clone_episode_lasts_every_scene_times_the_kept_clip(long_clone_creation):
    assert long_clone_creation.creation.episode.target_duration_s == 1190


@pytest.fixture
def failed_clone_creation(tmp_path):
    parts = build_clone_parts(tmp_path)
    parts.repository.add_episode.side_effect = RuntimeError("database gone")
    with pytest.raises(RuntimeError):
        parts.service.create_episode("p1", build_draft(source=CLONE, source_clone_id="k2"))
    creation = added_creation(parts)
    return [
        parts.files.episode_dir("p1", creation.episode.id),
        *(parts.files.character_dir(character.id) for character in creation.new_characters),
    ]


def test_a_failed_clone_creation_removes_every_copy(failed_clone_creation):
    assert [path.exists() for path in failed_clone_creation] == [False, False, False, False, False]


@pytest.fixture
def renumbered_creation(tmp_path):
    parts = build_parts(tmp_path)
    reloaded = build_episode(id="e5", number=5, title="Episode 5")

    def add_episode(creation):
        creation.episode.number = 5
        return creation.episode

    parts.repository.add_episode.side_effect = add_episode
    parts.repository.find_episode.return_value = reloaded
    summary = parts.service.create_episode("p1", build_draft())
    return SimpleNamespace(
        summary=summary,
        reloaded=reloaded,
        episode_id=added_creation(parts).episode.id,
        parts=parts,
    )


def test_a_number_taken_meanwhile_gets_its_own_default_title(renumbered_creation):
    renumbered_creation.parts.repository.update_episode.assert_called_once_with(
        renumbered_creation.episode_id, {"title": "Episode 5"}
    )


def test_a_renumbered_episode_is_returned_as_saved(renumbered_creation):
    assert renumbered_creation.summary.episode is renumbered_creation.reloaded


def build_part(part_id: str, position: int) -> EpisodePart:
    return EpisodePart(
        id=part_id,
        episode_id="e2",
        position=position,
        title=f"Part {position + 1} title",
        plan="Mai dives.",
        target_duration_s=60,
        recap=None,
    )


def build_scene(scene_id: str, part_id: str, **values) -> Scene:
    defaults = {
        "id": scene_id,
        "episode_id": "e2",
        "part_id": part_id,
        "position": 0,
        "image_prompt": "Mai at the pier",
        "video_prompt": "0-3s: Mai walks.",
        "narrator_text": None,
        "character_ids": [],
        "clip_duration_s": 8,
        "image_status": MediaStatus.NONE,
        "clip_status": MediaStatus.NONE,
        "narration_status": MediaStatus.NONE,
    }
    return Scene(**{**defaults, **values})


def build_open_request(request_id: str, kind: GenerationKind, scene_id: str | None):
    return GenerationRequest(
        id=request_id,
        kind=kind,
        episode_id="e2",
        scene_id=scene_id,
        status=GenerationStatus.QUEUED,
        params={},
    )


DETAIL_PARTS = [build_part("pt1", 0), build_part("pt2", 1), build_part("pt3", 2)]
DETAIL_SCENES = [
    build_scene(
        "s1",
        "pt1",
        image_status=MediaStatus.DONE,
        clip_status=MediaStatus.DONE,
        narration_status=MediaStatus.DONE,
        narrator_text="Mai dives.",
    ),
    build_scene(
        "s2",
        "pt1",
        image_status=MediaStatus.DONE,
        clip_status=MediaStatus.FAILED,
        narrator_text="  ",
    ),
    build_scene("s3", "pt1", image_status=MediaStatus.FAILED),
    build_scene("s4", "pt1", narration_status=MediaStatus.FAILED, narrator_text="The bell rings."),
    build_scene("s5", "pt2", image_status=MediaStatus.DONE),
]
MUSIC_REQUEST = build_open_request("r-music", GenerationKind.MUSIC, None)
CLIP_REQUEST = build_open_request("r-clip", GenerationKind.SCENE_CLIP, "s1")


def build_detail_parts(tmp_path, episode: Episode):
    parts = build_parts(tmp_path)
    parts.repository.find_episode.return_value = episode
    parts.repository.find_parts.return_value = DETAIL_PARTS
    parts.repository.find_scenes.return_value = DETAIL_SCENES
    parts.repository.find_open_requests_for_episode.return_value = [MUSIC_REQUEST, CLIP_REQUEST]
    parts.repository.find_latest_requests.return_value = []
    return parts


@pytest.fixture
def episode_detail(tmp_path):
    parts = build_detail_parts(tmp_path, build_episode())
    candidate_path = parts.files.thumbnail_candidate_path("p1", "e2", 1, "png")
    parts.repository.find_latest_requests.return_value = [
        build_request("t5", 1, GenerationStatus.DONE, output_path=str(candidate_path)),
        build_request("t6", 3, GenerationStatus.QUEUED),
        build_request("t2", 2, GenerationStatus.FAILED, error_message="Blocked"),
        build_request("t1", 1, GenerationStatus.FAILED, error_message="Old failure"),
        build_request("t0", 9, GenerationStatus.DONE),
    ]
    return SimpleNamespace(detail=parts.service.get_episode_detail("e2"), parts=parts)


def test_the_detail_holds_the_episode_its_project_and_the_requests_not_tied_to_a_scene(
    episode_detail,
):
    detail = episode_detail.detail
    assert (detail.summary.episode.id, detail.project.id, detail.open_requests) == (
        "e2",
        "p1",
        [MUSIC_REQUEST],
    )


def test_the_detail_lists_every_part_with_the_counters_of_its_scenes(episode_detail):
    assert episode_detail.detail.parts == [
        PartSummary(
            DETAIL_PARTS[0],
            PartCounts(
                scene_count=4,
                images_done=2,
                clips_done=1,
                narration_done=1,
                narration_with_text=2,
                failed_count=3,
                open_request_count=1,
            ),
        ),
        PartSummary(
            DETAIL_PARTS[1],
            PartCounts(
                scene_count=1,
                images_done=1,
                clips_done=0,
                narration_done=0,
                narration_with_text=0,
                failed_count=0,
                open_request_count=0,
            ),
        ),
        PartSummary(
            DETAIL_PARTS[2],
            PartCounts(
                scene_count=0,
                images_done=0,
                clips_done=0,
                narration_done=0,
                narration_with_text=0,
                failed_count=0,
                open_request_count=0,
            ),
        ),
    ]


def test_the_parts_and_scenes_are_read_for_the_episode(episode_detail):
    repository = episode_detail.parts.repository
    assert (repository.find_parts.call_args_list, repository.find_scenes.call_args_list) == (
        [call("e2")],
        [call("e2")],
    )


def test_thumbnail_candidates_show_the_newest_request_of_each_candidate(episode_detail):
    assert episode_detail.detail.thumbnail_candidates == [
        ThumbnailCandidate(
            1,
            GenerationStatus.DONE,
            "projects/p1/episodes/e2/output/thumbnail-candidate-1.png",
            None,
        ),
        ThumbnailCandidate(2, GenerationStatus.FAILED, None, "Blocked"),
        ThumbnailCandidate(3, GenerationStatus.QUEUED, None, None),
    ]


def test_thumbnail_requests_are_read_for_the_episode(episode_detail):
    episode_detail.parts.repository.find_latest_requests.assert_called_once_with(
        "e2", GenerationKind.THUMBNAIL
    )


@pytest.fixture(
    params=[
        (EpisodeSource.IDEA, {}, False),
        (EpisodeSource.FILM_ANALYSIS, {"fa-1": JOBS["fa-1"]}, False),
        (EpisodeSource.FILM_ANALYSIS, {}, True),
        (EpisodeSource.FILM_ANALYSIS, None, True),
        (EpisodeSource.FILM_CLONE, {"k2": CLONES["k2"]}, False),
        (EpisodeSource.FILM_CLONE, {}, True),
        (EpisodeSource.FILM_CLONE, None, True),
    ]
)
def source_deleted(request, tmp_path):
    source, sources_by_id, expected = request.param
    source_id = None if sources_by_id is None else "fa-1" if source is ANALYSIS else "k2"
    episode = build_episode(source=source, source_job_id=source_id, source_clone_id=source_id)
    parts = build_detail_parts(tmp_path, episode)
    parts.job_repository.find_by_id.side_effect = (sources_by_id or {}).get
    parts.clone_repository.find_by_id.side_effect = (sources_by_id or {}).get
    return Outcome(parts.service.get_episode_detail("e2").is_source_deleted, expected)


def test_the_detail_tells_whether_the_source_was_deleted(source_deleted):
    assert source_deleted.actual == source_deleted.expected


def build_update_parts(tmp_path, episode: Episode, project: FilmProject | None = None):
    parts = build_parts(tmp_path, project)
    parts.repository.find_episode.return_value = episode
    return parts


def updated_values(parts) -> dict:
    return parts.repository.update_episode.call_args.args[1]


@pytest.fixture(
    params=[
        (
            EpisodeStatus.RUNNING,
            {"title": "New title"},
            EpisodeRunningError,
            "Episode 2 is running — stop it first",
        ),
        (
            EpisodeStatus.RUNNING,
            {"stop_points": STOP_POINTS, "music_prompt": "x"},
            EpisodeRunningError,
            "Episode 2 is running — stop it first",
        ),
        (
            EpisodeStatus.PAUSED,
            {"idea": "Changed"},
            FilmConflictError,
            "Idea and target length can change only before the episode starts",
        ),
        (
            EpisodeStatus.DONE,
            {"target_duration_s": 24},
            FilmConflictError,
            "Idea and target length can change only before the episode starts",
        ),
        (
            EpisodeStatus.PAUSED,
            {"title": "  "},
            InvalidFilmRequestError,
            "Title must be 1-150 characters",
        ),
        (
            EpisodeStatus.DRAFT,
            {"target_duration_s": 7},
            InvalidFilmRequestError,
            TARGET_MESSAGE,
        ),
        (
            EpisodeStatus.DRAFT,
            {"target_duration_s": None},
            InvalidFilmRequestError,
            TARGET_MESSAGE,
        ),
        (EpisodeStatus.DRAFT, {"idea": ""}, InvalidFilmRequestError, IDEA_MESSAGE),
        (
            EpisodeStatus.PAUSED,
            {"summary": "x" * 10001},
            InvalidFilmRequestError,
            SUMMARY_MESSAGE,
        ),
        (
            EpisodeStatus.RUNNING,
            {"summary": "Mai finds the bell."},
            EpisodeRunningError,
            "Episode 2 is running — stop it first",
        ),
    ]
)
def rejected_update(request, tmp_path):
    status, changes, error_class, message = request.param
    parts = build_update_parts(tmp_path, build_episode(status=status))
    with pytest.raises(error_class) as error:
        parts.service.update_episode("e2", changes)
    return Outcome(
        actual=(str(error.value), parts.repository.update_episode.called),
        expected=(message, False),
    )


def test_an_invalid_edit_is_refused_and_writes_nothing(rejected_update):
    assert rejected_update.actual == rejected_update.expected


@pytest.fixture
def archived_update_error(tmp_path):
    parts = build_update_parts(
        tmp_path, build_episode(), build_project(status=ProjectStatus.ARCHIVED)
    )
    with pytest.raises(FilmConflictError) as error:
        parts.service.update_episode("e2", {"title": "New"})
    return error.value


def test_an_archived_project_refuses_episode_edits(archived_update_error):
    assert str(archived_update_error) == "Film project p1 is archived"


@pytest.fixture(
    params=[
        (
            EpisodeStatus.RUNNING,
            {"stop_points": {"afterScript": False}},
            {"stop_points": {"afterScript": False}},
        ),
        (
            EpisodeStatus.DRAFT,
            {"idea": " Changed ", "target_duration_s": 24, "title": " New title "},
            {"idea": "Changed", "target_duration_s": 24, "title": "New title"},
        ),
        (
            EpisodeStatus.DONE,
            {"burn_subtitles": True, "subtitle_style": SubtitleStyle.CLEAN_WHITE},
            {
                "burn_subtitles": True,
                "subtitle_style": SubtitleStyle.CLEAN_WHITE,
                "needs_assembly": True,
            },
        ),
        (
            EpisodeStatus.DONE,
            {"subtitle_style": SubtitleStyle.CLEAN_WHITE, "thumbnail_prompt": "  "},
            {"subtitle_style": SubtitleStyle.CLEAN_WHITE, "thumbnail_prompt": None},
        ),
        (
            EpisodeStatus.PAUSED,
            {"music_prompt": " Soft piano "},
            {"music_prompt": "Soft piano"},
        ),
        (
            EpisodeStatus.PAUSED,
            {"music_prompt": None},
            {
                "music_prompt": None,
                "music_status": MediaStatus.NONE,
                "music_path": None,
                "music_error": None,
            },
        ),
        (EpisodeStatus.DRAFT, {"target_duration_s": 3600}, {"target_duration_s": 3600}),
        (
            EpisodeStatus.DONE,
            {"summary": "  Mai finds the bell.  "},
            {"summary": "Mai finds the bell."},
        ),
        (EpisodeStatus.FAILED, {"summary": "   "}, {"summary": None}),
        (EpisodeStatus.PAUSED, {"summary": "x" * 10000}, {"summary": "x" * 10000}),
    ]
)
def accepted_update(request, tmp_path):
    status, changes, expected_values = request.param
    parts = build_update_parts(tmp_path, build_episode(status=status))
    parts.service.update_episode("e2", changes)
    return Outcome(updated_values(parts), expected_values)


def test_an_allowed_edit_writes_the_normalised_values(accepted_update):
    assert accepted_update.actual == accepted_update.expected


@pytest.fixture
def unchanged_update(tmp_path):
    parts = build_update_parts(tmp_path, build_episode())
    summary = parts.service.update_episode("e2", {"stop_points": None, "burn_subtitles": None})
    return SimpleNamespace(summary=summary, parts=parts)


def test_null_settings_change_nothing(unchanged_update):
    assert not unchanged_update.parts.repository.update_episode.called


def test_the_edit_answers_with_the_saved_episode(unchanged_update):
    assert unchanged_update.summary.episode.id == "e2"


@pytest.fixture
def music_prompt_update(tmp_path):
    parts = build_update_parts(
        tmp_path,
        build_episode(
            status=EpisodeStatus.DONE,
            music_status=MediaStatus.DONE,
            music_path="projects/p1/episodes/e2/music.mp3",
        ),
    )
    music_file = write_file(parts.files.music_path("p1", "e2", "mp3"), b"music")
    parts.service.update_episode("e2", {"music_prompt": "Slow cello"})
    return SimpleNamespace(values=updated_values(parts), music_file=music_file)


def test_a_new_music_prompt_resets_the_track_and_flags_assembly(music_prompt_update):
    assert music_prompt_update.values == {
        "music_prompt": "Slow cello",
        "music_status": MediaStatus.NONE,
        "music_path": None,
        "music_error": None,
        "needs_assembly": True,
    }


def test_a_new_music_prompt_deletes_the_track(music_prompt_update):
    assert not music_prompt_update.music_file.exists()


@pytest.fixture
def busy_delete(tmp_path):
    parts = build_update_parts(tmp_path, build_episode(status=EpisodeStatus.PAUSED))
    parts.repository.find_open_requests_for_episode.return_value = ["request-1"]
    with pytest.raises(FilmConflictError) as error:
        parts.service.delete_episode("e2")
    return SimpleNamespace(error=error.value, parts=parts)


def test_an_episode_with_generation_running_is_not_deleted(busy_delete):
    assert str(busy_delete.error) == "Episode 2 has generation running"


def test_a_refused_delete_removes_nothing(busy_delete):
    assert not busy_delete.parts.repository.delete_episode.called


@pytest.fixture
def deleted_episode(tmp_path):
    parts = build_update_parts(tmp_path, build_episode(status=EpisodeStatus.DONE))
    episode_dir = parts.files.episode_dir("p1", "e2")
    write_file(episode_dir / "scenes" / "s1" / "image.png", b"image")
    parts.service.delete_episode("e2")
    return SimpleNamespace(episode_dir=episode_dir, parts=parts)


def test_deleting_an_episode_removes_its_rows(deleted_episode):
    deleted_episode.parts.repository.delete_episode.assert_called_once_with("e2")


def test_deleting_an_episode_removes_its_folder(deleted_episode):
    assert not deleted_episode.episode_dir.exists()
