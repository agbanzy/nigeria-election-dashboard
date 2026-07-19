"""Integration tests: apply-and-approve API keys + the /api access gate."""

from __future__ import annotations

import dataclasses

import pytest

pytestmark = pytest.mark.integration


def _prod_app():
    """App with production-style key enforcement on."""
    import os

    from app import create_app
    from app.config import Config

    # A production app now requires ADMIN_TOKEN (fail-closed admin gate); set a
    # dummy so create_app's startup guard is satisfied.
    os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
    cfg = dataclasses.replace(Config.from_env(), env="production", api_key_enforcement=True)
    return create_app(cfg)


def test_gate_blocks_keyless_but_not_browser_or_exempt(db_engine):
    client = _prod_app().test_client()

    # Programmatic keyless request → 401 pointing at the application page.
    r = client.get("/api/states")
    assert r.status_code == 401
    assert "apply" in r.get_json()

    # Health stays open (uptime checks), methodology stays open (provenance).
    assert client.get("/api/health").status_code == 200

    # The dashboard's own browser traffic passes without a key.
    assert client.get("/api/states", headers={"Sec-Fetch-Site": "same-origin"}).status_code == 200
    assert (
        client.get("/api/states", headers={"Referer": "http://localhost/dashboard"}).status_code
        == 200
    )


def test_apply_approve_key_lifecycle(db_engine):
    client = _prod_app().test_client()

    r = client.post(
        "/api/developer/apply",
        json={"name": "Jane Dev", "email": "jane@example.com", "use_case": "research"},
    )
    assert r.status_code == 201
    ref = r.get_json()["application_ref"]

    # Duplicate application must not leak the original ref.
    r = client.post(
        "/api/developer/apply",
        json={"name": "Mallory", "email": "jane@example.com", "use_case": "stealing refs"},
    )
    assert r.status_code == 409
    assert "application_ref" not in r.get_json()

    # Pending → no key yet.
    r = client.post("/api/developer/status", json={"application_ref": ref})
    assert r.get_json()["status"] == "pending"
    assert "api_key" not in r.get_json()

    # Admin approves. The admin gate is fail-closed, so these calls must carry
    # the X-Admin-Token (a keyless admin call is now rejected).
    admin_hdr = {"X-Admin-Token": "test-admin-token"}
    assert client.get("/api/admin/api-clients").status_code == 401  # no token → denied
    clients = client.get("/api/admin/api-clients", headers=admin_hdr).get_json()["clients"]
    cid = clients[0]["client_id"]
    r = client.post(
        f"/api/admin/api-clients/{cid}/decision", json={"action": "approve"}, headers=admin_hdr
    )
    assert r.status_code == 200

    # Applicant retrieves the key with their ref.
    r = client.post("/api/developer/status", json={"application_ref": ref})
    key = r.get_json()["api_key"]
    assert key and key.startswith("ned_")

    # Keyed programmatic access passes; a bad key does not.
    assert client.get("/api/states", headers={"X-API-Key": key}).status_code == 200
    assert client.get("/api/states", headers={"X-API-Key": "ned_bogus"}).status_code == 401

    # Revocation kills the key immediately.
    client.post(
        f"/api/admin/api-clients/{cid}/decision", json={"action": "revoke"}, headers=admin_hdr
    )
    assert client.get("/api/states", headers={"X-API-Key": key}).status_code == 401


def test_apply_validation(db_engine):
    client = _prod_app().test_client()

    assert client.post("/api/developer/apply", json={}).status_code == 400
    assert (
        client.post(
            "/api/developer/apply",
            json={"name": "X", "email": "not-an-email", "use_case": "y"},
        ).status_code
        == 400
    )
    assert (
        client.post("/api/developer/status", json={"application_ref": "nope"}).status_code == 404
    )
