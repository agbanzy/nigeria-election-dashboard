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
    import logging
    import os

    from sqlalchemy import text as _text

    log = logging.getLogger("alembic.runtime.migration")

    preferred_schema = os.environ.get("DB_SCHEMA", "elections")

    config.set_main_option("sqlalchemy.url", _url())
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        schema: str | None = None
        if connection.dialect.name == "postgresql":
            user = connection.execute(_text("SELECT current_user")).scalar()
            log.info("alembic: connected as user=%s", user)

            # Strategy 1: use preferred schema if it already exists (regardless of
            # whether the current role owns it — the role just needs table-level
            # privileges, which DO grants automatically).
            already_exists = connection.execute(
                _text("SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname = :s)"),
                {"s": preferred_schema},
            ).scalar()
            if already_exists:
                schema = preferred_schema
                log.info("alembic: schema %r already exists, using it", schema)
            else:
                # Strategy 2: pick any schema the role can CREATE in.
                writable = connection.execute(
                    _text(
                        "SELECT n.nspname FROM pg_namespace n "
                        "WHERE has_schema_privilege(current_user, n.nspname, 'CREATE') "
                        "AND n.nspname NOT IN ('pg_catalog','information_schema','pg_toast') "
                        "ORDER BY (n.nspname = current_user) DESC, (n.nspname = :pref) DESC, n.nspname"
                    ),
                    {"pref": preferred_schema},
                ).fetchall()
                log.info("alembic: schemas user can CREATE in: %s", [r[0] for r in writable])

                if writable:
                    schema = writable[0][0]
                    log.info("alembic: using schema with CREATE privilege=%s", schema)
                else:
                    # Strategy 3: try to create our preferred schema (needs CREATE on db).
                    try:
                        connection.execute(
                            _text(f'CREATE SCHEMA IF NOT EXISTS "{preferred_schema}" AUTHORIZATION CURRENT_USER')
                        )
                        connection.commit()
                        schema = preferred_schema
                        log.info("alembic: created schema=%s", schema)
                    except Exception as exc:
                        connection.rollback()
                        log.error("alembic: cannot create schema %r: %s", preferred_schema, exc)
                        raise RuntimeError(
                            f"Postgres role {user!r} has no CREATE privilege on any schema and cannot "
                            f"create new ones. Grant CREATE on the database, or pre-create the "
                            f"{preferred_schema!r} schema owned by this role via the DO console."
                        ) from exc

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
