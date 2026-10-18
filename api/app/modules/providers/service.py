from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.db import utc_now
from app.modules.providers.claude_cli_check import ClaudeCliCheck, ClaudeCliStatus
from app.modules.providers.connection_tester import (
    ConnectionCheck,
    ProviderConnectionTester,
)
from app.modules.providers.errors import (
    ProviderNotFoundError,
    ProviderNotSetUpError,
    SecretKeyMissingError,
)
from app.modules.providers.flow_extension import FlowExtensionBridge
from app.modules.providers.model_catalog import CatalogModel, find_catalog_models, resolve_model
from app.modules.providers.models import Provider
from app.modules.providers.provider_catalog import (
    DEFAULT_PROVIDER_BY_ROUTE,
    IMAGE_MEDIA_KINDS,
    PROVIDER_SPECS,
    PROVIDER_SPECS_BY_ID,
    MediaFeature,
    MediaKind,
    ProviderId,
    ProviderKind,
    ProviderSpec,
    RouteName,
    default_pacing,
)
from app.modules.providers.provider_rules import (
    ProviderUpdate,
    Unset,
    validate_provider_update,
)
from app.modules.providers.repository import ProviderRepository
from app.modules.providers.secret_box import SecretBox, to_last_visible_chars

NOT_SET_UP_TEST_ERROR = "Not set up"


@dataclass(frozen=True)
class ProviderQueueCounts:
    queued: int
    processing: int
    failed_last_24h: int


EMPTY_QUEUE_COUNTS = ProviderQueueCounts(queued=0, processing=0, failed_last_24h=0)


class ProviderQueueCounter(Protocol):
    def count_by_provider(self) -> dict[str, ProviderQueueCounts]: ...


class ChosenProviderSettings(Protocol):
    def get_chosen_image_provider(self, feature: MediaFeature) -> ProviderId | None: ...

    def get_chosen_clip_provider(self) -> ProviderId | None: ...


@dataclass(frozen=True)
class ConnectionTestResult:
    is_ok: bool
    error: str | None
    tested_at: datetime


@dataclass(frozen=True)
class FlowProviderState:
    is_extension_connected: bool
    paused_until: datetime | None
    flow_project_id: str | None


@dataclass(frozen=True)
class ProviderView:
    spec: ProviderSpec
    has_key: bool
    api_key_last4: str | None
    is_key_unreadable: bool
    base_url: str | None
    models: dict[str, str]
    catalog: dict[MediaKind, tuple[CatalogModel, ...]]
    max_concurrent: int
    min_interval_s: int
    is_set_up: bool
    queue: ProviderQueueCounts
    last_test: ConnectionTestResult | None
    flow: FlowProviderState | None
    cli_status: ClaudeCliStatus | None


@dataclass(frozen=True)
class ProviderSettingsView:
    provider_ids_by_route: dict[str, str]
    providers: list[ProviderView]
    is_secret_key_set: bool


@dataclass(frozen=True)
class ProviderPacing:
    max_concurrent: int
    min_interval_s: int


@dataclass(frozen=True)
class ProviderAccess:
    provider_id: ProviderId
    name: str
    api_key: str | None
    base_url: str | None
    models: Mapping[MediaKind, CatalogModel]
    flow_project_id: str | None


@dataclass(frozen=True)
class ProviderSettingTools:
    secret_box: SecretBox
    connection_tester: ProviderConnectionTester
    extension: FlowExtensionBridge
    queue_counter: ProviderQueueCounter
    claude_cli_check: ClaudeCliCheck
    chosen_provider_settings: ChosenProviderSettings


class ProviderSettingService:
    def __init__(self, repository: ProviderRepository, tools: ProviderSettingTools):
        self._repository = repository
        self._tools = tools

    def ensure_providers(self) -> None:
        existing_ids = {provider.id for provider in self._repository.find_all()}
        missing_providers = [
            _build_default_provider(spec) for spec in PROVIDER_SPECS if spec.id not in existing_ids
        ]
        if missing_providers:
            self._repository.add_all(missing_providers)

    def get_settings_view(self) -> ProviderSettingsView:
        providers_by_id = {provider.id: provider for provider in self._repository.find_all()}
        queue_counts_by_provider = self._tools.queue_counter.count_by_provider()
        return ProviderSettingsView(
            provider_ids_by_route=self.get_route_provider_ids(),
            providers=[
                self._to_view(
                    spec,
                    providers_by_id[spec.id],
                    queue_counts_by_provider.get(spec.id, EMPTY_QUEUE_COUNTS),
                )
                for spec in PROVIDER_SPECS
                if spec.id in providers_by_id
            ],
            is_secret_key_set=self._tools.secret_box.is_ready,
        )

    def update_provider(self, provider_id: str, update: ProviderUpdate) -> ProviderView:
        spec, provider = self._get_provider(provider_id)
        validate_provider_update(spec, update)
        self._repository.update_fields(spec.id, self._to_stored_values(provider, update))
        return self.get_provider_view(provider_id)

    def get_provider_view(self, provider_id: str) -> ProviderView:
        spec, provider = self._get_provider(provider_id)
        queue_counts = self._tools.queue_counter.count_by_provider().get(
            spec.id, EMPTY_QUEUE_COUNTS
        )
        return self._to_view(spec, provider, queue_counts)

    def resume_google_flow(self) -> ProviderView:
        self._tools.extension.resume()
        return self.get_provider_view(ProviderId.GOOGLE_FLOW)

    def open_flow_tab(self) -> None:
        self._tools.extension.open_flow_tab()

    def get_route_provider_ids(self) -> dict[str, str]:
        stored_ids = self._repository.find_route_provider_ids()
        return {
            route.value: stored_ids.get(route.value, default_id.value)
            for route, default_id in DEFAULT_PROVIDER_BY_ROUTE.items()
        }

    def to_stored_models(
        self, model_ids_by_provider: Mapping[str, Mapping[str, str]]
    ) -> dict[str, dict[str, str]]:
        return {
            provider_id: self._to_stored_provider_models(provider_id, model_ids_by_kind)
            for provider_id, model_ids_by_kind in model_ids_by_provider.items()
        }

    def test_connection(self, provider_id: str) -> ConnectionTestResult:
        spec, provider = self._get_provider(provider_id)
        result = self._run_connection_test(spec, provider)
        self._repository.update_fields(
            spec.id,
            {
                "last_test_at": result.tested_at,
                "last_test_ok": result.is_ok,
                "last_test_error": result.error,
            },
        )
        return result

    def pick_provider(self, media_kind: MediaKind, feature: MediaFeature) -> ProviderId:
        if media_kind is MediaKind.SPEECH:
            return self._route_provider(RouteName.SPEECH)
        if media_kind is MediaKind.MUSIC:
            return self._route_provider(RouteName.MUSIC)
        if media_kind in IMAGE_MEDIA_KINDS:
            return self._pick_image_provider(feature)
        return self._pick_clip_provider()

    def get_pacing(self, provider_id: ProviderId) -> ProviderPacing:
        _spec, provider = self._get_provider(provider_id)
        return ProviderPacing(
            max_concurrent=provider.max_concurrent, min_interval_s=provider.min_interval_s
        )

    def get_access(self, provider_id: ProviderId) -> ProviderAccess:
        spec, provider = self._get_provider(provider_id)
        api_key = self._read_api_key(provider)
        if not self._is_set_up(spec, provider, api_key):
            raise ProviderNotSetUpError(spec.name)
        return ProviderAccess(
            provider_id=spec.id,
            name=spec.name,
            api_key=api_key,
            base_url=provider.base_url,
            models={
                media_kind: resolve_model(spec.id, media_kind, provider.models.get(media_kind))
                for media_kind in spec.media_kinds
            },
            flow_project_id=provider.flow_project_id,
        )

    def is_set_up(self, provider_id: ProviderId) -> bool:
        spec, provider = self._get_provider(provider_id)
        return self._is_set_up(spec, provider, self._read_api_key(provider))

    def find_api_key(self, provider_id: ProviderId) -> str | None:
        _spec, provider = self._get_provider(provider_id)
        return self._read_api_key(provider)

    def _route_provider(self, route: RouteName) -> ProviderId:
        return ProviderId(self.get_route_provider_ids()[route.value])

    def _pick_image_provider(self, feature: MediaFeature) -> ProviderId:
        chosen_id = self._tools.chosen_provider_settings.get_chosen_image_provider(feature)
        return chosen_id or self._route_provider(RouteName.IMAGE)

    def _pick_clip_provider(self) -> ProviderId:
        chosen_id = self._tools.chosen_provider_settings.get_chosen_clip_provider()
        return chosen_id or self._route_provider(RouteName.VIDEO)

    def _to_stored_provider_models(
        self, provider_id: str, model_ids_by_kind: Mapping[str, str]
    ) -> dict[str, str]:
        spec, provider = self._get_provider(provider_id)
        update = ProviderUpdate(models=model_ids_by_kind)
        validate_provider_update(spec, update)
        return self._to_stored_values(provider, update)["models"]

    def _get_provider(self, provider_id: str) -> tuple[ProviderSpec, Provider]:
        if provider_id not in ProviderId.__members__.values():
            raise ProviderNotFoundError(provider_id)
        provider = self._repository.find_by_id(provider_id)
        if provider is None:
            raise ProviderNotFoundError(provider_id)
        return PROVIDER_SPECS_BY_ID[ProviderId(provider_id)], provider

    def _run_connection_test(self, spec: ProviderSpec, provider: Provider) -> ConnectionTestResult:
        if spec.kind is ProviderKind.CLI:
            return self._test_claude_cli()
        api_key = self._read_api_key(provider)
        if not self._is_set_up(spec, provider, api_key):
            return ConnectionTestResult(
                is_ok=False, error=NOT_SET_UP_TEST_ERROR, tested_at=utc_now()
            )
        outcome = self._tools.connection_tester.test(
            ConnectionCheck(spec=spec, api_key=api_key, base_url=provider.base_url)
        )
        return ConnectionTestResult(is_ok=outcome.is_ok, error=outcome.error, tested_at=utc_now())

    def _test_claude_cli(self) -> ConnectionTestResult:
        cli_check = self._tools.claude_cli_check
        status = cli_check.check()
        return ConnectionTestResult(
            is_ok=status is ClaudeCliStatus.SIGNED_IN,
            error=cli_check.describe_failure(status),
            tested_at=utc_now(),
        )

    def _to_stored_values(self, provider: Provider, update: ProviderUpdate) -> dict[str, Any]:
        values: dict[str, Any] = {}
        if isinstance(update.api_key, str):
            values.update(self._encrypt_api_key(update.api_key.strip()))
        elif update.api_key is None:
            values.update(api_key_encrypted=None, api_key_last4=None)
        if not isinstance(update.base_url, Unset):
            values["base_url"] = update.base_url
        if not isinstance(update.models, Unset):
            values["models"] = {**provider.models, **update.models}
        if not isinstance(update.flow_project_id, Unset):
            values["flow_project_id"] = update.flow_project_id
        if not isinstance(update.max_concurrent, Unset):
            values["max_concurrent"] = update.max_concurrent
        if not isinstance(update.min_interval_s, Unset):
            values["min_interval_s"] = update.min_interval_s
        return values

    def _encrypt_api_key(self, api_key: str) -> dict[str, Any]:
        if not self._tools.secret_box.is_ready:
            raise SecretKeyMissingError()
        return {
            "api_key_encrypted": self._tools.secret_box.encrypt(api_key),
            "api_key_last4": to_last_visible_chars(api_key),
        }

    def _read_api_key(self, provider: Provider) -> str | None:
        if provider.api_key_encrypted is None:
            return None
        return self._tools.secret_box.decrypt(provider.api_key_encrypted)

    def _is_set_up(self, spec: ProviderSpec, provider: Provider, api_key: str | None) -> bool:
        if spec.kind is ProviderKind.API:
            return api_key is not None
        if spec.kind is ProviderKind.LOCAL:
            return bool(provider.base_url)
        return True

    def _to_view(
        self, spec: ProviderSpec, provider: Provider, queue_counts: ProviderQueueCounts
    ) -> ProviderView:
        api_key = self._read_api_key(provider)
        has_key = provider.api_key_encrypted is not None
        return ProviderView(
            spec=spec,
            has_key=has_key,
            api_key_last4=provider.api_key_last4,
            is_key_unreadable=has_key and api_key is None,
            base_url=provider.base_url,
            models=dict(provider.models),
            catalog={
                media_kind: find_catalog_models(spec.id, media_kind)
                for media_kind in spec.media_kinds
                if find_catalog_models(spec.id, media_kind)
            },
            max_concurrent=provider.max_concurrent,
            min_interval_s=provider.min_interval_s,
            is_set_up=self._is_set_up(spec, provider, api_key),
            queue=queue_counts,
            last_test=_to_test_result(provider),
            flow=self._to_flow_state(spec, provider),
            cli_status=self._find_cli_status(spec),
        )

    def _find_cli_status(self, spec: ProviderSpec) -> ClaudeCliStatus | None:
        if spec.kind is not ProviderKind.CLI:
            return None
        return self._tools.claude_cli_check.get_recent_status()

    def _to_flow_state(self, spec: ProviderSpec, provider: Provider) -> FlowProviderState | None:
        if spec.kind is not ProviderKind.EXTENSION:
            return None
        return FlowProviderState(
            is_extension_connected=self._tools.extension.is_connected(),
            paused_until=self._tools.extension.paused_until(),
            flow_project_id=provider.flow_project_id,
        )


def _build_default_provider(spec: ProviderSpec) -> Provider:
    pacing = default_pacing(spec)
    return Provider(
        id=spec.id.value,
        models={},
        max_concurrent=pacing.max_concurrent,
        min_interval_s=pacing.min_interval_s,
    )


def _to_test_result(provider: Provider) -> ConnectionTestResult | None:
    if provider.last_test_at is None:
        return None
    return ConnectionTestResult(
        is_ok=bool(provider.last_test_ok),
        error=provider.last_test_error,
        tested_at=provider.last_test_at,
    )
