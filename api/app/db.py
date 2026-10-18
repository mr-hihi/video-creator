from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Text, create_engine
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


MICROSECOND_PRECISION = 6
LONG_TEXT_TYPE = Text().with_variant(mysql.MEDIUMTEXT(), "mysql")


def build_string_enum_type(enum_class: type[StrEnum], length: int) -> Enum:
    return Enum(
        enum_class,
        native_enum=False,
        length=length,
        values_callable=lambda members: [member.value for member in members],
    )


class UtcDateTime(TypeDecorator[datetime]):
    # MySQL DATETIME drops the offset, so values are stored as naive UTC and re-tagged on read.
    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "mysql":
            return dialect.type_descriptor(mysql.DATETIME(fsp=MICROSECOND_PRECISION))
        return dialect.type_descriptor(DateTime())

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    engine = create_engine(database_url, pool_pre_ping=True, pool_recycle=3600)
    return sessionmaker(bind=engine, expire_on_commit=False)
