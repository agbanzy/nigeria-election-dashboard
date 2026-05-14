"""GET /api/health — used by DO App Platform's healthcheck."""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify
from sqlalchemy import select, text

from app.db import session_scope
from app.models import ScrapeLog

bp = Blueprint("health", __name__, url_prefix="/api")


@bp.get("/health")
def health() -> tuple:
    db_status = "error"
    scraper_last_run: str | None = None
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
            db_status = "ok"
            last = session.scalar(
                select(ScrapeLog).order_by(ScrapeLog.created_at.desc()).limit(1)
            )
            if last and last.created_at:
                scraper_last_run = last.created_at.isoformat()
    except Exception as exc:  # noqa: BLE001
        return (
            jsonify(
                {
                    "status": "degraded",
                    "db": db_status,
                    "error": str(exc),
                    "now": datetime.now(timezone.utc).isoformat(),
                }
            ),
            503,
        )
    return (
        jsonify(
            {
                "status": "ok",
                "db": db_status,
                "scraper_last_run": scraper_last_run,
                "now": datetime.now(timezone.utc).isoformat(),
            }
        ),
        200,
    )


@bp.get("/")
def index():
    return jsonify(
        {
            "service": "ng-election-dashboard",
            "docs": "/api/health",
        }
    )
