"""Integration test for /api/health — boots Postgres + applies migrations + calls Flask."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_health_returns_ok(db_engine):
    from app import create_app

    app = create_app()
    client = app.test_client()
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["db"] == "ok"


def test_overview_empty_db(db_engine):
    from app import create_app

    app = create_app()
    client = app.test_client()
    resp = client.get("/api/overview")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["totals"]["states"] == 0
    assert data["totals"]["elections"] == 0


def test_states_list_after_seed(db_engine):
    from app import create_app
    from app.seed import seed

    seed()
    app = create_app()
    client = app.test_client()
    resp = client.get("/api/states")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 37
    codes = {row["code"] for row in data}
    assert "FC" in codes
    assert "LA" in codes


def test_calendar_next_after_seed(db_engine):
    from app import create_app
    from app.seed import seed

    seed()
    app = create_app()
    client = app.test_client()
    resp = client.get("/api/calendar/next")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data is not None
    assert "election_date" in data
    assert "seconds_until" in data
