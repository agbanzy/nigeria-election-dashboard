"""Alembic env for the pan-Nigeria election dashboard."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import normalize_database_url
from app.db import Base
from app import models  # noqa: F401 — ensure models are registered with Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    return normalize_database_url(os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url") or ""))


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    import os

    from sqlalchemy import text as _text

    schema = os.environ.get("DB_SCHEMA", "elections")

    config.set_main_option("sqlalchemy.url", _url())
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # DO managed PG 15 dev tier: app role can't write to `public`. Create a
        # schema we own and target it for everything (alembic_version + tables).
        if connection.dialect.name == "postgresql":
            connection.execute(_text(f'CREATE SCHEMA IF NOT EXISTS "{schema}" AUTHORIZATION CURRENT_USER'))
            connection.execute(_text(f'SET search_path TO "{schema}", public'))
            connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=schema if connection.dialect.name == "postgresql" else None,
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
