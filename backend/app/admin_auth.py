"""Shared admin-token gate for write / operator endpoints.

Fail **closed**: when ``ADMIN_TOKEN`` is unset the gate denies every request.
A missing or omitted secret must never silently open admin writes to the
public internet — the previous fail-*open* posture (return True when unset)
meant one spec redeploy or console slip exposed unauthenticated vote-tally
falsification. The app factory additionally refuses to boot in production
without a token (see ``create_app``), so the unset state is unreachable there.

Comparisons use ``hmac.compare_digest`` to avoid a timing oracle on the token.
"""

from __future__ import annotations

import hmac
import os

from flask import request


def admin_token_configured() -> bool:
    """True when a non-empty ADMIN_TOKEN is set in the environment."""
    return bool(os.environ.get("ADMIN_TOKEN", "").strip())


def require_admin() -> bool:
    """Constant-time check of the X-Admin-Token header. Fails closed."""
    expected = os.environ.get("ADMIN_TOKEN", "").strip()
    if not expected:
        return False  # fail closed — no token configured means deny, not allow
    given = request.headers.get("X-Admin-Token", "")
    return hmac.compare_digest(given, expected)
