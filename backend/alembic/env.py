from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from applify.config import get_settings
from applify.db import models  # registers tables on Base.metadata
from applify.db.session import Base

config = context.config
# Tests pass their own database URL; otherwise use the app settings.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
# Alembic owns the app tables and the raw layer; the analytics schemas belong to the
# pipeline (features) and dbt (staging, marts).
OWN_SCHEMAS = {None, "public", models.RAW_SCHEMA}


def include_name(name: str | None, type_: str, parent_names: object) -> bool:
    return name in OWN_SCHEMAS if type_ == "schema" else True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
