"""SQLAlchemy engine + session factory.

Single global engine, lazy-initialized via `init_engine()` from the app factory or CLI entry.
Use `session_scope()` for short-lived transactions in request handlers and scripts.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import normalize_database_url


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def init_engine(database_url: str, *, echo: bool = False) -> Engine:
    global _engine, _SessionLocal
    url = normalize_database_url(database_url)
    _engine = create_engine(url, echo=echo, pool_pre_ping=True, future=True)
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
