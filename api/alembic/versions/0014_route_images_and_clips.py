"""move the image and clip sources into the image and video routes; give Film Clone its own input mode

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-18
"""

from collections.abc import Collection, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

IMAGE_SOURCE_KEY = "imageSource"
CLIP_SOURCE_KEY = "clipSource"
INPUT_MODE_KEY = "inputMode"
FILM_CLONE_INPUT_MODE_KEY = "filmCloneInputMode"
CHOSEN_PROVIDER_KEYS = (
    "filmCloneImageProvider",
    "filmStudioImageProvider",
    "filmStudioClipProvider",
)
API_IMAGE_ROUTE = "apiImage"
API_VIDEO_ROUTE = "apiVideo"
IMAGE_ROUTE = "image"
VIDEO_ROUTE = "video"
GOOGLE_FLOW_SOURCE = "google_flow"
API_SOURCE = "api"
LOCAL_SOURCE = "local"
GOOGLE_FLOW_PROVIDER = "google_flow"
LOCAL_IMAGE_PROVIDER = "sd_webui"
OLD_DEFAULT_API_PROVIDER = "google"

app_settings = sa.table(
    "app_settings",
    sa.column("key", sa.String),
    sa.column("value", sa.JSON),
    sa.column("updated_at", sa.DateTime),
)
provider_routes = sa.table(
    "provider_routes",
    sa.column("route", sa.String),
    sa.column("provider_id", sa.String),
    sa.column("updated_at", sa.DateTime),
)


def upgrade() -> None:
    settings = _find_settings((IMAGE_SOURCE_KEY, CLIP_SOURCE_KEY, INPUT_MODE_KEY))
    routes = _find_routes((API_IMAGE_ROUTE, API_VIDEO_ROUTE))
    provider_ids_by_route = {
        IMAGE_ROUTE: _to_image_route_provider(
            settings.get(IMAGE_SOURCE_KEY), routes.get(API_IMAGE_ROUTE)
        ),
        VIDEO_ROUTE: _to_video_route_provider(
            settings.get(CLIP_SOURCE_KEY), routes.get(API_VIDEO_ROUTE)
        ),
    }
    _delete_settings((IMAGE_SOURCE_KEY, CLIP_SOURCE_KEY, FILM_CLONE_INPUT_MODE_KEY))
    _delete_routes((API_IMAGE_ROUTE, API_VIDEO_ROUTE, IMAGE_ROUTE, VIDEO_ROUTE))
    _insert_routes(provider_ids_by_route)
    if INPUT_MODE_KEY in settings:
        _insert_settings({FILM_CLONE_INPUT_MODE_KEY: settings[INPUT_MODE_KEY]})


def downgrade() -> None:
    routes = _find_routes((IMAGE_ROUTE, VIDEO_ROUTE))
    image_provider = routes.get(IMAGE_ROUTE, GOOGLE_FLOW_PROVIDER)
    video_provider = routes.get(VIDEO_ROUTE, GOOGLE_FLOW_PROVIDER)
    image_source = _to_image_source(image_provider)
    clip_source = _to_clip_source(video_provider)
    _delete_settings(
        (IMAGE_SOURCE_KEY, CLIP_SOURCE_KEY, FILM_CLONE_INPUT_MODE_KEY, *CHOSEN_PROVIDER_KEYS)
    )
    _delete_routes((IMAGE_ROUTE, VIDEO_ROUTE, API_IMAGE_ROUTE, API_VIDEO_ROUTE))
    _insert_settings({IMAGE_SOURCE_KEY: image_source, CLIP_SOURCE_KEY: clip_source})
    api_provider_ids_by_route = {}
    if image_source == API_SOURCE:
        api_provider_ids_by_route[API_IMAGE_ROUTE] = image_provider
    if clip_source == API_SOURCE:
        api_provider_ids_by_route[API_VIDEO_ROUTE] = video_provider
    _insert_routes(api_provider_ids_by_route)


def _to_image_route_provider(image_source: Any, api_image_provider: str | None) -> str:
    if image_source == LOCAL_SOURCE:
        return LOCAL_IMAGE_PROVIDER
    if image_source == API_SOURCE:
        return api_image_provider or OLD_DEFAULT_API_PROVIDER
    return GOOGLE_FLOW_PROVIDER


def _to_video_route_provider(clip_source: Any, api_video_provider: str | None) -> str:
    if clip_source == API_SOURCE:
        return api_video_provider or OLD_DEFAULT_API_PROVIDER
    return GOOGLE_FLOW_PROVIDER


def _to_image_source(image_provider: str) -> str:
    if image_provider == GOOGLE_FLOW_PROVIDER:
        return GOOGLE_FLOW_SOURCE
    if image_provider == LOCAL_IMAGE_PROVIDER:
        return LOCAL_SOURCE
    return API_SOURCE


def _to_clip_source(video_provider: str) -> str:
    return GOOGLE_FLOW_SOURCE if video_provider == GOOGLE_FLOW_PROVIDER else API_SOURCE


def _find_settings(keys: Collection[str]) -> dict[str, Any]:
    rows = op.get_bind().execute(
        sa.select(app_settings.c.key, app_settings.c.value).where(app_settings.c.key.in_(keys))
    )
    return {key: value for key, value in rows}


def _find_routes(routes: Collection[str]) -> dict[str, str]:
    rows = op.get_bind().execute(
        sa.select(provider_routes.c.route, provider_routes.c.provider_id).where(
            provider_routes.c.route.in_(routes)
        )
    )
    return {route: provider_id for route, provider_id in rows}


def _delete_settings(keys: Collection[str]) -> None:
    op.execute(app_settings.delete().where(app_settings.c.key.in_(keys)))


def _delete_routes(routes: Collection[str]) -> None:
    op.execute(provider_routes.delete().where(provider_routes.c.route.in_(routes)))


def _insert_settings(values_by_key: Mapping[str, Any]) -> None:
    updated_at = _utc_now()
    op.bulk_insert(
        app_settings,
        [
            {"key": key, "value": value, "updated_at": updated_at}
            for key, value in values_by_key.items()
        ],
    )


def _insert_routes(provider_ids_by_route: Mapping[str, str]) -> None:
    if not provider_ids_by_route:
        return
    updated_at = _utc_now()
    op.bulk_insert(
        provider_routes,
        [
            {"route": route, "provider_id": provider_id, "updated_at": updated_at}
            for route, provider_id in provider_ids_by_route.items()
        ],
    )


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
