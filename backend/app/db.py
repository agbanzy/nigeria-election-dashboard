"""SQLAlchemy engine + session factory.

Single global engine, lazy-initialized via `init_engine()` from the app factory or CLI entry.
Use `session_scope()` for short-lived transactions in request handlers and scripts.

Schema model: DO managed Postgres 15 dev tier hands the app a non-owner role
that can't write to the `public` schema. We use an `elections` schema we create
and own ourselves. Override with `DB_SCHEMA` env var if needed.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import normalize_database_url


SCHEMA_NAME = os.environ.get("DB_SCHEMA", "elections")


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def init_engine(database_url: str, *, echo: bool = False) -> Engine:
    global _engine, _SessionLocal
    url = normalize_database_url(database_url)
    _engine = create_engine(url, echo=echo, pool_pre_ping=True, future=True)

    # Every new connection pins search_path to our schema so unqualified table
    # references resolve correctly. Postgres-only — no-op for SQLite tests.
    @event.listens_for(_engine, "connect")
    def _set_search_path(dbapi_conn, _conn_record):  # type: ignore[no-untyped-def]
        if _engine is None or _engine.dialect.name != "postgresql":
            return
        cur = dbapi_conn.cursor()
        try:
            cur.execute(f'SET search_path TO "{SCHEMA_NAME}", public')
        finally:
            cur.close()

    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("DB engine not initialized; call init_engine() first")
    return _engine


def get_session() -> Session:
    if _SessionLocal is None:
        raise RuntimeError("Session factory not initialized; call init_engine() first")
    return _SessionLocal()


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def healthcheck() -> dict[str, Any]:
    try:
        with session_scope() as s:
            s.execute(_dialect_now_sql())
        return {"db": "ok"}
    except Exception as exc:
        return {"db": "error", "error": str(exc)}


def _dialect_now_sql():  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    return text("SELECT 1")
