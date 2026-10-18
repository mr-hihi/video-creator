from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context
from app.config import get_settings
from app.db import Base
from app.modules.app_settings import models as app_setting_models  # noqa: F401
from app.modules.film_clones import models as film_clone_models  # noqa: F401
from app.modules.films import models as film_models  # noqa: F401
from app.modules.jobs import models  # noqa: F401
from app.modules.media_generation import models as generation_models  # noqa: F401
from app.modules.prompt_presets import models as prompt_preset_models  # noqa: F401
from app.modules.providers import models as provider_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
database_url = get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(database_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
