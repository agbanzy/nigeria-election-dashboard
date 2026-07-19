"""Pytest fixtures.

Pure-Python tests (analysis, normalizers) run without Postgres.
Integration tests use a `pg` fixture that boots a Postgres container via
testcontainers and runs Alembic migrations against it.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest


@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    """Boot a Postgres testcontainer and yield its connection URL.

    Skips the test session if Docker is unavailable.
    """
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers not installed")

    with PostgresContainer("postgres:15-alpine") as pg:
        # testcontainers hands back a psycopg2 URL; this app uses psycopg 3.
        url = pg.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql://"
        ).replace("postgresql://", "postgresql+psycopg://")
        os.environ["DATABASE_URL"] = url
        yield url


@pytest.fixture
def db_engine(pg_url: str):
    from alembic import command
    from alembic.config import Config as AlembicConfig

    from app.db import init_engine

    engine = init_engine(pg_url)

    cfg = AlembicConfig(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "migrations"))
    cfg.set_main_option("sqlalchemy.url", pg_url)
    command.upgrade(cfg, "head")
    yield engine
    command.downgrade(cfg, "base")
