from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UtcDateTime, utc_now


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    api_key_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    api_key_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    models: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    max_concurrent: Mapped[int] = mapped_column(Integer)
    min_interval_s: Mapped[int] = mapped_column(Integer, default=0)
    flow_project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_test_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_test_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)


class ProviderRoute(Base):
    __tablename__ = "provider_routes"

    route: Mapped[str] = mapped_column(String(20), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(20))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utc_now, onupdate=utc_now)
