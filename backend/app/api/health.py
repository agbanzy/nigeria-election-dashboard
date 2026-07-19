"""GET /api/health — liveness for DO App Platform's container healthcheck.

Two distinct concerns, deliberately separated:

* ``/api/health`` reports **web+db** liveness (DO restarts the web container on a
  non-200 here — so a *scraper* problem must NOT fail it, or DO would pointlessly
  bounce the web tier). It still surfaces scraper staleness in the body for
  dashboards to read.
* ``/api/health/scraper`` returns 503 when the scraper *should* be producing data
  (calendar mode live/preflight) but hasn't recently — point an uptime alert at
  this so a dead/wedged scraper serving hours-old "live" results is caught,
  instead of the old check that returned 200 as long as ``SELECT 1`` worked.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from flask import Blueprint, jsonify
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db import session_scope
from app.models import ScrapeLog

bp = Blueprint("health", __name__, url_prefix="/api")

# Consider the scraper stale once the last run is older than this multiple of
# the mode's expected interval (only when it's supposed to be active).
STALE_INTERVAL_MULTIPLIER = 3


def _scraper_status(session: Session) -> dict[str, Any]:
    """Best-effort scraper staleness. Never raises — health must stay robust."""
    last_run: datetime | None = None
    try:
        last = session.scalar(
            select(ScrapeLog).order_by(ScrapeLog.created_at.desc()).limit(1)
        )
        if last and last.created_at:
            last_run = last.created_at
    except Exception:  # noqa: BLE001
        return {"mode": "unknown", "last_run": None, "age_seconds": None, "stale": False}

    mode = "unknown"
    interval: int | None = None
    try:
        from app.scraper.calendar import decide_mode

        decision = decide_mode(session)
        mode, interval = decision.mode, decision.interval_seconds
    except Exception:  # noqa: BLE001
        pass

    age_seconds: float | None = None
    stale = False
    expected_active = mode in ("live", "preflight")
    if last_run is not None:
        age_seconds = (datetime.now(UTC) - last_run).total_seconds()
        if expected_active and interval:
            stale = age_seconds > interval * STALE_INTERVAL_MULTIPLIER
    elif expected_active:
        stale = True  # should be running and has never produced a scrape

    return {
        "mode": mode,
        "last_run": last_run.isoformat() if last_run else None,
        "age_seconds": round(age_seconds) if age_seconds is not None else None,
        "stale": stale,
    }


@bp.get("/health")
def health() -> tuple[Any, int]:
    now = datetime.now(UTC).isoformat()
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
            scraper = _scraper_status(session)
    except Exception as exc:  # noqa: BLE001
        return (
            jsonify({"status": "degraded", "db": "error", "error": str(exc), "now": now}),
            503,
        )
    # Web tier is healthy whenever db is reachable — scraper staleness is
    # reported but never fails this check (see module docstring).
    return (
        jsonify(
            {
                "status": "ok",
                "db": "ok",
                "scraper_last_run": scraper["last_run"],
                "scraper": scraper,
                "now": now,
            }
        ),
        200,
    )


@bp.get("/health/scraper")
def scraper_health() -> tuple[Any, int]:
    """Dedicated staleness probe for alerting (503 when stale)."""
    now = datetime.now(UTC).isoformat()
    try:
        with session_scope() as session:
            scraper = _scraper_status(session)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"status": "error", "error": str(exc), "now": now}), 503
    status_code = 503 if scraper["stale"] else 200
    return jsonify({"status": "stale" if scraper["stale"] else "ok", "scraper": scraper, "now": now}), status_code


@bp.get("/")
def index() -> Any:
    return jsonify({"service": "ng-election-dashboard", "docs": "/api/health"})
