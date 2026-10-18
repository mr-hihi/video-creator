from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.modules.providers.claude_cli_check import ClaudeCliStatus
from app.modules.providers.model_catalog import CatalogModel
from app.modules.providers.provider_catalog import MediaKind, ProviderId, ProviderKind
from app.modules.providers.provider_rules import UNSET, ProviderUpdate
from app.modules.providers.service import (
    ConnectionTestResult,
    ProviderQueueCounts,
    ProviderSettingsView,
    ProviderView,
)

CAMEL_CASE_CONFIG = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class UpdateProviderRequest(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    api_key: str | None = None
    base_url: str | None = None
    flow_project_id: str | None = None
    max_concurrent: int | None = None
    min_interval_s: int | None = None

    def to_update(self) -> ProviderUpdate:
        given_fields = self.model_fields_set
        return ProviderUpdate(
            api_key=self.api_key if "api_key" in given_fields else UNSET,
            base_url=self.base_url if "base_url" in given_fields else UNSET,
            flow_project_id=(self.flow_project_id if "flow_project_id" in given_fields else UNSET),
            max_concurrent=UNSET if self.max_concurrent is None else self.max_concurrent,
            min_interval_s=UNSET if self.min_interval_s is None else self.min_interval_s,
        )


class ConnectionTestResponse(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    ok: bool
    error: str | None
    tested_at: datetime

    @classmethod
    def from_result(cls, result: ConnectionTestResult) -> "ConnectionTestResponse":
        return cls(ok=result.is_ok, error=result.error, tested_at=result.tested_at)


class CatalogModelResponse(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    id: str
    label: str
    is_default: bool
    clip_lengths: list[int] | None
    max_references: int | None

    @classmethod
    def from_model(cls, model: CatalogModel, is_default: bool) -> "CatalogModelResponse":
        return cls(
            id=model.id,
            label=model.label,
            is_default=is_default,
            clip_lengths=list(model.clip_lengths_s) or None,
            max_references=model.max_references,
        )


class QueueCountsResponse(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    queued: int
    processing: int
    failed_last24h: int = Field(alias="failedLast24h")

    @classmethod
    def from_counts(cls, counts: ProviderQueueCounts) -> "QueueCountsResponse":
        return cls(
            queued=counts.queued,
            processing=counts.processing,
            failed_last24h=counts.failed_last_24h,
        )


class ProviderResponse(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    id: ProviderId
    name: str
    kind: ProviderKind
    media_kinds: list[MediaKind]
    has_key: bool
    api_key_last4: str | None
    key_unreadable: bool
    base_url: str | None
    models: dict[str, str]
    catalog: dict[str, list[CatalogModelResponse]]
    max_concurrent: int
    min_interval_s: int
    set_up: bool
    queue: QueueCountsResponse
    last_test: ConnectionTestResponse | None
    extension_connected: bool | None = None
    paused_until: datetime | None = None
    flow_project_id: str | None = None
    cli_status: ClaudeCliStatus | None = None

    @classmethod
    def from_view(cls, view: ProviderView) -> "ProviderResponse":
        return cls(
            id=view.spec.id,
            name=view.spec.name,
            kind=view.spec.kind,
            media_kinds=list(view.spec.media_kinds),
            has_key=view.has_key,
            api_key_last4=view.api_key_last4,
            key_unreadable=view.is_key_unreadable,
            base_url=view.base_url,
            models=view.models,
            catalog={
                media_kind.value: [
                    CatalogModelResponse.from_model(model, is_default=position == 0)
                    for position, model in enumerate(models)
                ]
                for media_kind, models in view.catalog.items()
            },
            max_concurrent=view.max_concurrent,
            min_interval_s=view.min_interval_s,
            set_up=view.is_set_up,
            queue=QueueCountsResponse.from_counts(view.queue),
            last_test=(
                None
                if view.last_test is None
                else ConnectionTestResponse.from_result(view.last_test)
            ),
            extension_connected=None if view.flow is None else view.flow.is_extension_connected,
            paused_until=None if view.flow is None else view.flow.paused_until,
            flow_project_id=None if view.flow is None else view.flow.flow_project_id,
            cli_status=view.cli_status,
        )


class ProviderSettingsResponse(BaseModel):
    model_config = CAMEL_CASE_CONFIG

    routes: dict[str, str]
    providers: list[ProviderResponse]
    secret_key_set: bool

    @classmethod
    def from_view(cls, view: ProviderSettingsView) -> "ProviderSettingsResponse":
        return cls(
            routes=view.provider_ids_by_route,
            providers=[ProviderResponse.from_view(provider) for provider in view.providers],
            secret_key_set=view.is_secret_key_set,
        )
