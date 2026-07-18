"""API access gate — dashboard free for all, programmatic API by (free) approval.

Requests to /api/* pass when any of these hold:

1. The path is exempt (auth, admin, developer, health, methodology — each has
   its own gate or is deliberately open).
2. The request is the dashboard's own browser traffic — same-origin fetch
   metadata (`Sec-Fetch-Site: same-origin`) or an Origin/Referer whose host
   matches the request host. This is an access-management signal, not a
   security boundary: the data is free either way, keys exist so API usage is
   attributable and contactable.
3. A valid `X-API-Key` header (issued via /api/developer) is present.
4. Enforcement is off (local dev default — see Config.api_key_enforcement).

Everything else gets a 401 that explains how to apply.
"""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse

from flask import Flask, jsonify, request
from sqlalchemy import select

from app.config import Config

EXEMPT_PREFIXES = (
    "/api/auth",
    "/api/admin",
    "/api/developer",
    "/api/health",
    "/api/methodology",
)

APPLY_URL = "https://elections.innoedgetech.com/api-access"


def _is_same_origin() -> bool:
    if request.headers.get("Sec-Fetch-Site") == "same-origin":
        return True
    source = request.headers.get("Origin") or request.headers.get("Referer") or ""
    host = urlparse(source).netloc
    return bool(host) and host == request.host


def _check_key(key: str) -> bool:
    from app.db import session_scope
    from app.models import ApiClient

    with session_scope() as session:
        client = session.scalar(
            select(ApiClient).where(ApiClient.api_key == key, ApiClient.status == "approved")
        )
        if not client:
            return False
        client.last_used_at = datetime.now(UTC)
        client.request_count += 1
        return True


def install_api_gate(app: Flask, cfg: Config) -> None:
    @app.before_request
    def _gate() -> object:
        path = request.path
        if not path.startswith("/api/"):
            return None
        if any(path.startswith(p) for p in EXEMPT_PREFIXES):
            return None
        if request.method == "OPTIONS":
            return None
        if _is_same_origin():
            return None

        key = request.headers.get("X-API-Key", "").strip()
        if key:
            if _check_key(key):
                return None
            return jsonify(
                {
                    "error": "invalid or revoked API key",
                    "apply": APPLY_URL,
                }
            ), 401

        if not cfg.api_key_enforcement:
            return None

        return jsonify(
            {
                "error": "API key required",
                "message": (
                    "The dashboard and its data are free for everyone. "
                    "Programmatic API access is also free — apply for a key "
                    f"and send it as an X-API-Key header. Apply at {APPLY_URL}."
                ),
                "apply": APPLY_URL,
                "docs": "https://github.com/agbanzy/nigeria-election-dashboard/blob/main/docs/API.md",
            }
        ), 401
