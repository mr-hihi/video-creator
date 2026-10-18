from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from app.modules.media_generation.clip_segments import (
    ClipPlan,
    build_segment_prompt,
    plan_clip_segments,
)
from app.modules.media_generation.media_task import (
    MediaInputs,
    MediaTask,
    ProviderError,
    ProviderErrorKind,
)
from app.modules.media_generation.models import GenerationRequest
from app.modules.providers.model_catalog import CatalogModel
from app.modules.providers.provider_catalog import MediaKind, ProviderId
from app.modules.providers.service import ProviderAccess

REFERENCES_KEY = "references"
SOURCE_IMAGE_KEY = "sourceImage"
START_FRAME_KEY = "startFrame"
VOICE_SAMPLE_KEY = "voiceSample"
CONSENT_CLIP_KEY = "consentClip"
ASPECT_PARAM = "aspect"
CLIP_LENGTH_PARAM = "clipLengthS"
LANGUAGE_PARAM = "language"
MIN_LENGTH_PARAM = "minLengthS"
SAMPLE_TEXT_PARAM = "sampleText"
REFERENCE_NAMES_PARAM = "referenceNames"
REFERENCE_KINDS_PARAM = "referenceKinds"
MODEL_PARAM = "model"
VOICE_NAME_PARAM = "voiceName"
SAMPLE_DURATION_PARAM = "sampleDurationS"
PROVIDER_VOICE_ID_PARAM = "providerVoiceId"
ELEVENLABS_MIN_SAMPLE_S = 60
GOOGLE_SAMPLE_RANGE_S = (10, 30)
DROPPED_REFERENCES_PARAM = "droppedReferences"
PASS_PARAM = "pass"
PASSES_PARAM = "passes"
PASS_RESULT_PATH_PARAM = "passResultPath"
SEGMENT_PARAM = "segment"
SEGMENTS_PARAM = "segments"
SEGMENT_LENGTHS_PARAM = "segmentLengths"
PASS_PROMPT = (
    "Keep the scene, the framing and everyone else unchanged. Make {name} look like the reference "
    "image."
)
FALLBACK_REFERENCE_NAME = "the character"
COMPOSITE_PROVIDERS = frozenset({ProviderId.SD_WEBUI})


@dataclass(frozen=True)
class BuiltTask:
    task: MediaTask
    sent_params: dict[str, Any]
    pass_count: int
    reference_names: tuple[str, ...]
    clip_plan: ClipPlan | None = None


def build_media_task(request: GenerationRequest, access: ProviderAccess) -> BuiltTask:
    model = access.models[request.media_kind]
    clip_length_s = request.params.get(CLIP_LENGTH_PARAM)
    clip_plan = (
        None if clip_length_s is None else plan_clip_segments(clip_length_s, model.clip_lengths_s)
    )
    if request.media_kind is MediaKind.SPEECH:
        _ensure_voice_fits(access.provider_id, request)
    all_references = list(request.input_paths.get(REFERENCES_KEY, []))
    pass_count = count_passes(access.provider_id, model, len(all_references))
    kept_references, dropped_references = (
        (all_references, [])
        if pass_count > 1 or access.provider_id in COMPOSITE_PROVIDERS
        else split_references(all_references, model.max_references)
    )
    task = MediaTask(
        request_id=request.id,
        media_kind=request.media_kind,
        model=model,
        api_key=access.api_key,
        base_url=access.base_url,
        prompt=request.prompt,
        inputs=_to_media_inputs(request.input_paths, kept_references),
        aspect=request.params.get(ASPECT_PARAM),
        clip_length_s=None if clip_plan is None else clip_plan.segment_lengths_s[0],
        language=request.params.get(LANGUAGE_PARAM),
        min_length_s=_cap_track_length(model, request.params.get(MIN_LENGTH_PARAM)),
        sample_text=request.params.get(SAMPLE_TEXT_PARAM),
        flow_project_id=access.flow_project_id,
        reference_kinds=tuple(request.params.get(REFERENCE_KINDS_PARAM, [])),
        voice_name=request.params.get(VOICE_NAME_PARAM),
        provider_voice_id=request.params.get(PROVIDER_VOICE_ID_PARAM),
    )
    sent_params = {**request.params, MODEL_PARAM: model.id}
    if dropped_references:
        sent_params[DROPPED_REFERENCES_PARAM] = dropped_references
    return BuiltTask(
        task=task,
        sent_params=sent_params,
        pass_count=pass_count,
        reference_names=tuple(request.params.get(REFERENCE_NAMES_PARAM, [])),
        clip_plan=clip_plan,
    )


def count_passes(provider_id: ProviderId, model: CatalogModel, reference_count: int) -> int:
    if provider_id in COMPOSITE_PROVIDERS or not model.max_references:
        return 1
    if reference_count <= model.max_references:
        return 1
    return reference_count


def build_pass_task(built: BuiltTask, pass_number: int, previous_result: Path | None) -> MediaTask:
    task = built.task
    reference = task.inputs.references[pass_number - 1]
    if pass_number == 1:
        return replace(task, inputs=replace(task.inputs, references=(reference,)))
    reference_name = (
        built.reference_names[pass_number - 1]
        if pass_number <= len(built.reference_names)
        else FALLBACK_REFERENCE_NAME
    )
    return replace(
        task,
        prompt=PASS_PROMPT.format(name=reference_name),
        inputs=replace(task.inputs, references=(reference,), source_image=previous_result),
    )


def build_segment_task(built: BuiltTask, number: int, start_frame: Path | None) -> MediaTask:
    task = built.task
    plan = built.clip_plan
    if plan is None or plan.segment_count == 1:
        return task
    return replace(
        task,
        prompt=build_segment_prompt(plan, number, task.prompt),
        clip_length_s=plan.segment_lengths_s[number - 1],
        inputs=replace(task.inputs, start_frame=start_frame),
    )


def split_references(
    reference_paths: list[str], max_references: int | None
) -> tuple[list[str], list[str]]:
    if max_references is None:
        return list(reference_paths), []
    return list(reference_paths[:max_references]), list(reference_paths[max_references:])


def _ensure_voice_fits(provider_id: ProviderId, request: GenerationRequest) -> None:
    voice_name = request.params.get(VOICE_NAME_PARAM, "")
    sample_s = round(request.params.get(SAMPLE_DURATION_PARAM) or 0)
    if provider_id is ProviderId.ELEVENLABS and sample_s < ELEVENLABS_MIN_SAMPLE_S:
        raise ProviderError(
            f"ElevenLabs needs a voice sample of at least {ELEVENLABS_MIN_SAMPLE_S} s; "
            f"'{voice_name}' is {sample_s} s",
            ProviderErrorKind.FATAL,
        )
    if provider_id is not ProviderId.GOOGLE:
        return
    if request.input_paths.get(CONSENT_CLIP_KEY) is None:
        raise ProviderError(
            f"Google AI needs a consent clip for '{voice_name}' — add it in the library",
            ProviderErrorKind.FATAL,
        )
    shortest_s, longest_s = GOOGLE_SAMPLE_RANGE_S
    if not shortest_s <= sample_s <= longest_s:
        raise ProviderError(
            f"Google AI needs a voice sample of {shortest_s}-{longest_s} s; "
            f"'{voice_name}' is {sample_s} s",
            ProviderErrorKind.FATAL,
        )


def _cap_track_length(model: CatalogModel, min_length_s: int | None) -> int | None:
    if min_length_s is None or model.longest_track_s is None:
        return min_length_s
    return min(min_length_s, model.longest_track_s)


def _to_media_inputs(input_paths: Mapping[str, Any], references: list[str]) -> MediaInputs:
    return MediaInputs(
        references=tuple(Path(path) for path in references),
        source_image=_to_optional_path(input_paths.get(SOURCE_IMAGE_KEY)),
        start_frame=_to_optional_path(input_paths.get(START_FRAME_KEY)),
        voice_sample=_to_optional_path(input_paths.get(VOICE_SAMPLE_KEY)),
        consent_clip=_to_optional_path(input_paths.get(CONSENT_CLIP_KEY)),
    )


def _to_optional_path(value: str | None) -> Path | None:
    return None if value is None else Path(value)
