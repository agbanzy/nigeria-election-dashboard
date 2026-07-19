"""POST /api/scrape/trigger, GET /api/scrape/status — operator endpoints.

Write/operator actions are gated by `X-Admin-Token` via the shared fail-closed
admin gate (see app.admin_auth).
"""

from __future__ import annotations

from flask import Blueprint, jsonify
from sqlalchemy import select

from app.admin_auth import require_admin as _require_admin
from app.db import session_scope
from app.models import ScrapeLog
from app.scraper.calendar import decide_mode

bp = Blueprint("scrape", __name__, url_prefix="/api/scrape")


@bp.get("/status")
def status():
    with session_scope() as session:
        decision = decide_mode(session)
        last = session.scalar(
            select(ScrapeLog).order_by(ScrapeLog.created_at.desc()).limit(1)
        )
        return jsonify(
            {
                "mode": decision.mode,
                "interval_seconds": decision.interval_seconds,
                "active_state_ids": sorted(decision.state_ids),
                "next_event": (
                    {
                        "date": decision.next_event.election_date.isoformat()
                        if decision.next_event and decision.next_event.election_date
                        else None,
                        "type": decision.next_event.election_type if decision.next_event else None,
                        "state_id": decision.next_event.state_id if decision.next_event else None,
                    }
                    if decision.next_event
                    else None
                ),
                "last_log": (
                    {
                        "phase": last.phase,
                        "status": last.status,
                        "created_at": last.created_at.isoformat() if last.created_at else None,
                    }
                    if last
                    else None
                ),
            }
        )


@bp.post("/trigger")
def trigger():
    if not _require_admin():
        return jsonify({"error": "unauthorized"}), 401
    # Phase A: cannot actually trigger a worker run from the web process.
    # Operator must invoke `python -m app.scraper.backfill` on the worker
    # container directly (e.g. via `doctl apps run`).
    return (
        jsonify(
            {
                "ok": False,
                "message": (
                    "Web process cannot reach the worker. Run "
                    "`doctl apps run <app> --component scraper -- python -m app.scraper.backfill`"
                ),
            }
        ),
        202,
    )
