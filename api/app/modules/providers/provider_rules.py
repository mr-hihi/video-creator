import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from app.modules.providers.errors import InvalidProviderSettingError
from app.modules.providers.model_catalog import find_catalog_models
from app.modules.providers.provider_catalog import (
    PROVIDER_SPECS_BY_ID,
    ROUTE_CHOICES,
    MediaKind,
    ProviderId,
    ProviderKind,
    ProviderSpec,
    RouteName,
)

MAX_API_KEY_LENGTH = 500
MAX_CONCURRENT_LOWER_LIMIT = 1
MAX_CONCURRENT_UPPER_LIMIT = 10
MIN_INTERVAL_UPPER_LIMIT_S = 600
URL_SCHEMES = ("http://", "https://")
MODEL_FREE_KINDS = frozenset({ProviderKind.LOCAL, ProviderKind.CLI})


class Unset:
    pass


UNSET: Final = Unset()


@dataclass(frozen=True)
class ProviderUpdate:
    api_key: str | None | Unset = UNSET
    base_url: str | None | Unset = UNSET
    models: Mapping[str, str] | Unset = UNSET
    flow_project_id: str | None | Unset = UNSET
    max_concurrent: int | Unset = UNSET
    min_interval_s: int | Unset = UNSET


def validate_provider_update(spec: ProviderSpec, update: ProviderUpdate) -> None:
    _validate_fields_fit_the_kind(spec, update)
    if (
        isinstance(update.api_key, str)
        and not 1 <= len(update.api_key.strip()) <= MAX_API_KEY_LENGTH
    ):
        raise InvalidProviderSettingError(f"API key must be 1-{MAX_API_KEY_LENGTH} characters")
    if isinstance(update.base_url, str) and not update.base_url.startswith(URL_SCHEMES):
        raise InvalidProviderSettingError("Base URL must start with http:// or https://")
    if isinstance(update.models, Mapping):
        _validate_catalog_models(spec, update.models)
    if isinstance(update.flow_project_id, str) and not _is_uuid(update.flow_project_id):
        raise InvalidProviderSettingError("Flow project id must be a UUID")
    _validate_pacing(update)


def validate_routes(provider_ids_by_route: Mapping[str, str]) -> None:
    for route, provider_id in provider_ids_by_route.items():
        if route not in RouteName.__members__.values():
            raise InvalidProviderSettingError(f"Unknown route '{route}'")
        if provider_id not in ROUTE_CHOICES[RouteName(route)]:
            raise InvalidProviderSettingError(
                f"{_to_provider_name(provider_id)} cannot serve {route}"
            )


def _validate_fields_fit_the_kind(spec: ProviderSpec, update: ProviderUpdate) -> None:
    misfit_fields = []
    if not isinstance(update.api_key, Unset) and spec.kind is not ProviderKind.API:
        misfit_fields.append("apiKey")
    if not isinstance(update.base_url, Unset) and spec.kind is not ProviderKind.LOCAL:
        misfit_fields.append("baseUrl")
    if isinstance(update.models, Mapping) and spec.kind in MODEL_FREE_KINDS:
        misfit_fields.append("models")
    if isinstance(update.models, Mapping) and spec.kind not in MODEL_FREE_KINDS:
        misfit_fields.extend(
            f"models.{media_kind}"
            for media_kind in update.models
            if media_kind not in spec.media_kinds or media_kind == MediaKind.ANALYSIS
        )
    if not isinstance(update.flow_project_id, Unset) and spec.id is not ProviderId.GOOGLE_FLOW:
        misfit_fields.append("flowProjectId")
    if not isinstance(update.max_concurrent, Unset) and spec.kind is ProviderKind.CLI:
        misfit_fields.append("maxConcurrent")
    if not isinstance(update.min_interval_s, Unset) and spec.kind is ProviderKind.CLI:
        misfit_fields.append("minIntervalS")
    if misfit_fields:
        raise InvalidProviderSettingError(f"{misfit_fields[0]} does not apply to {spec.name}")


def _validate_catalog_models(spec: ProviderSpec, model_ids_by_kind: Mapping[str, str]) -> None:
    for media_kind, model_id in model_ids_by_kind.items():
        catalog_ids = {model.id for model in find_catalog_models(spec.id, MediaKind(media_kind))}
        if model_id not in catalog_ids:
            raise InvalidProviderSettingError(
                f"Unknown model '{model_id}' for {spec.name} {media_kind}"
            )


def _validate_pacing(update: ProviderUpdate) -> None:
    if isinstance(update.max_concurrent, int) and not (
        MAX_CONCURRENT_LOWER_LIMIT <= update.max_concurrent <= MAX_CONCURRENT_UPPER_LIMIT
    ):
        raise InvalidProviderSettingError(
            f"Concurrent requests must be between {MAX_CONCURRENT_LOWER_LIMIT} and "
            f"{MAX_CONCURRENT_UPPER_LIMIT}"
        )
    if isinstance(update.min_interval_s, int) and not (
        0 <= update.min_interval_s <= MIN_INTERVAL_UPPER_LIMIT_S
    ):
        raise InvalidProviderSettingError(
            f"Interval must be between 0 and {MIN_INTERVAL_UPPER_LIMIT_S} seconds"
        )


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _to_provider_name(provider_id: str) -> str:
    if provider_id in ProviderId.__members__.values():
        return PROVIDER_SPECS_BY_ID[ProviderId(provider_id)].name
    return provider_id
