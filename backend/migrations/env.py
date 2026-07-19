"""Alembic env for the pan-Nigeria election dashboard."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import models  # noqa: F401 — ensure models are registered with Base.metadata
from app.config import normalize_database_url
from app.db import Base

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


def _resolve_schema(connection, preferred_schema, log):
    """Decide which schema migrations should target, with full diagnostics.

    DO App Platform dev databases hand the app a non-owner role. Over time DO
    has tightened defaults so the role may have DML on existing tables (the app
    works) but no CREATE on any schema (migrations break). This routine logs the
    exact privilege picture and picks the most sensible target:

      1. An explicit DB_SCHEMA env override that the role can CREATE in.
      2. The schema where the app's existing tables already live (if the role
         can CREATE there — it usually can, since it created them originally).
      3. Any schema the role can CREATE in (prefer one named after the role).
      4. Attempt to create the preferred schema.
      5. Give up and let the default search_path apply (logged as an error so
         the failure is actionable).
    """
    from sqlalchemy import text as _text

    user = connection.execute(_text("SELECT current_user")).scalar()
    db = connection.execute(_text("SELECT current_database()")).scalar()
    search_path = connection.execute(_text("SHOW search_path")).scalar()
    log.info("alembic-diag: user=%s database=%s search_path=%s", user, db, search_path)

    # Where do existing app tables live? 'states' is created by migration 0001.
    existing = connection.execute(
        _text(
            "SELECT table_schema, count(*) FROM information_schema.tables "
            "WHERE table_name IN ('states','elections','election_results','alembic_version') "
            "GROUP BY table_schema"
        )
    ).fetchall()
    log.info("alembic-diag: existing app tables by schema: %s", [(r[0], r[1]) for r in existing])

    # Privilege picture across all non-system schemas.
    privs = connection.execute(
        _text(
            "SELECT n.nspname, "
            "has_schema_privilege(current_user, n.nspname, 'CREATE') AS can_create, "
            "has_schema_privilege(current_user, n.nspname, 'USAGE') AS can_use, "
            "pg_get_userbyid(n.nspowner) AS owner "
            "FROM pg_namespace n "
            "WHERE n.nspname NOT IN ('pg_catalog','information_schema','pg_toast') "
            "ORDER BY n.nspname"
        )
    ).fetchall()
    for r in privs:
        log.info("alembic-diag: schema=%s create=%s usage=%s owner=%s", r[0], r[1], r[2], r[3])

    creatable = [r[0] for r in privs if r[1]]
    tables_schema = existing[0][0] if existing else None

    # Strategy 1: explicit override the role can write to.
    if preferred_schema and preferred_schema in creatable:
        log.info("alembic: using DB_SCHEMA override=%s", preferred_schema)
        return preferred_schema

    # Strategy 2: the schema the app's tables already live in (keeps everything
    # together) — but only if the role can CREATE there.
    if tables_schema and tables_schema in creatable:
        log.info("alembic: using existing-tables schema=%s", tables_schema)
        return tables_schema

    # Strategy 3: any creatable schema, preferring one named after the role.
    if creatable:
        creatable.sort(key=lambda s: (s != user, s != preferred_schema, s))
        log.info("alembic: using creatable schema=%s (options=%s)", creatable[0], creatable)
        return creatable[0]

    # Strategy 4: try to create the preferred schema (needs CREATE on database).
    target = preferred_schema or "elections"
    try:
        connection.execute(
            _text(f'CREATE SCHEMA IF NOT EXISTS "{target}" AUTHORIZATION CURRENT_USER')
        )
        connection.commit()
        log.info("alembic: created schema=%s", target)
        return target
    except Exception as exc:
        connection.rollback()
        log.error(
            "alembic: role %r cannot CREATE in any schema and cannot create new ones (%s). "
            "Existing app tables are in schema %r. Grant CREATE to this role on that schema "
            "(GRANT CREATE ON SCHEMA %s TO %s) from a privileged DB user, or point DATABASE_URL "
            "at a managed cluster where this role owns its schema.",
            user, exc, tables_schema, tables_schema or "public", user,
        )
        # If existing tables live somewhere, target that schema anyway — the
        # CREATE will fail loudly with the actionable message above, but at
        # least we won't silently scatter into the wrong schema.
        return tables_schema


def run_migrations_online() -> None:
    import logging
    import os

    from sqlalchemy import text as _text

    log = logging.getLogger("alembic.runtime.migration")

    # DB_SCHEMA="" (the app default in db.py) means "use the role's default
    # search_path". Migrations must follow the same default so they target the
    # same schema the running app does.
    preferred_schema = os.environ.get("DB_SCHEMA", "")

    config.set_main_option("sqlalchemy.url", _url())
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        schema: str | None = None
        if connection.dialect.name == "postgresql":
            schema = _resolve_schema(connection, preferred_schema, log)
            if schema:
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
