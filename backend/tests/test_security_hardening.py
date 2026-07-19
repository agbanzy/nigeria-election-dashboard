"""Tests for the 2026-07-19 audit security/reliability hardening.

Covers: fail-closed admin gate + constant-time compare (F-201/F-706), the
production ADMIN_TOKEN startup guard (F-201), SSRF host filtering on the OCR
fetch (F-202), login rate limiting (F-203/F-703), and the semantic scraper
health probe (F-402).
"""

from __future__ import annotations

import dataclasses
import os

import pytest

# ── Pure unit: admin gate fails closed + constant-time (no DB) ────────────────

def test_require_admin_fails_closed_when_unset():
    from app import create_app
    from app.admin_auth import require_admin
    from app.config import Config
    from app.db import init_engine

    init_engine("sqlite://")
    app = create_app(dataclasses.replace(Config.from_env(), env="development"))

    os.environ.pop("ADMIN_TOKEN", None)
    with app.test_request_context(headers={"X-Admin-Token": "anything"}):
        assert require_admin() is False  # unset → deny, never allow


def test_require_admin_matches_only_correct_token():
    from app import create_app
    from app.admin_auth import require_admin
    from app.config import Config
    from app.db import init_engine

    init_engine("sqlite://")
    app = create_app(dataclasses.replace(Config.from_env(), env="development"))

    os.environ["ADMIN_TOKEN"] = "s3cret-token"
    try:
        with app.test_request_context(headers={"X-Admin-Token": "s3cret-token"}):
            assert require_admin() is True
        with app.test_request_context(headers={"X-Admin-Token": "wrong"}):
            assert require_admin() is False
        with app.test_request_context():  # no header
            assert require_admin() is False
    finally:
        os.environ.pop("ADMIN_TOKEN", None)


def test_production_boot_requires_admin_token():
    from app import create_app
    from app.config import Config
    from app.db import init_engine

    init_engine("sqlite://")
    os.environ.pop("ADMIN_TOKEN", None)
    with pytest.raises(RuntimeError, match="ADMIN_TOKEN"):
        create_app(dataclasses.replace(Config.from_env(), env="production"))

    os.environ["ADMIN_TOKEN"] = "x" * 16
    try:
        create_app(dataclasses.replace(Config.from_env(), env="production"))  # boots fine
    finally:
        os.environ.pop("ADMIN_TOKEN", None)


# ── Pure unit: SSRF host filter (IP literals, no real DNS) ────────────────────

@pytest.mark.parametrize(
    "host,allowed",
    [
        ("8.8.8.8", True),        # public
        ("127.0.0.1", False),     # loopback
        ("10.0.0.1", False),      # RFC1918
        ("192.168.1.1", False),   # RFC1918
        ("169.254.169.254", False),  # cloud metadata (link-local)
        ("0.0.0.0", False),       # unspecified
    ],
)
def test_ssrf_host_filter(host, allowed):
    from app.api.admin import _is_public_host

    assert _is_public_host(host) is allowed


def test_fetch_remote_image_rejects_non_http_scheme():
    from app.api.admin import _fetch_remote_image

    content, err = _fetch_remote_image("file:///etc/passwd")
    assert content is None
    assert err is not None


# ── Integration: login rate limit (F-203/F-703) ───────────────────────────────

@pytest.mark.integration
def test_login_is_rate_limited(db_engine):
    import dataclasses as dc

    from app import create_app
    from app.config import Config

    os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
    app = create_app(dc.replace(Config.from_env(), env="production"))
    client = app.test_client()

    # Limit is "10 per minute" — the 11th+ within the window must be throttled.
    codes = [
        client.post("/api/auth/login", json={"email": "x@y.z", "password": "nope"}).status_code
        for _ in range(15)
    ]
    assert 429 in codes, f"expected a 429 among {codes}"


# ── Integration: semantic scraper health (F-402) ──────────────────────────────

@pytest.mark.integration
def test_scraper_health_reports_stale(db_engine):
    import dataclasses as dc
    from datetime import UTC, datetime, timedelta

    from app import create_app
    from app.config import Config
    from app.db import session_scope
    from app.models import ElectionCalendar, ScrapeLog, State

    with session_scope() as session:
        # A live election today → scraper is expected to be active.
        session.add(State(state_id=15, code="FC", name="FCT", zone="NC"))
        session.flush()
        session.add(
            ElectionCalendar(
                election_date=datetime.now(UTC).date(),
                election_type="presidential",
                status="live",
                state_id=15,
            )
        )
        # Last scrape is hours old → stale.
        session.add(
            ScrapeLog(status="ok", created_at=datetime.now(UTC) - timedelta(hours=3))
        )

    app = create_app(dc.replace(Config.from_env(), env="development"))
    resp = app.test_client().get("/api/health/scraper")
    assert resp.status_code == 503
    assert resp.get_json()["scraper"]["stale"] is True

    # The main health check stays 200 (web liveness) but surfaces the staleness.
    main = app.test_client().get("/api/health")
    assert main.status_code == 200
    assert main.get_json()["scraper"]["stale"] is True
