"""GET /api/sync/status — visibility into the sync queue."""

from __future__ import annotations

from flask import Blueprint, jsonify
from sqlalchemy import func, select

from app.db import session_scope
from app.models import Election, IrevRawCache
from app.scraper import sync as sync_mod

bp = Blueprint("sync", __name__, url_prefix="/api/sync")


@bp.get("/status")
def status():
    with session_scope() as session:
        depth = sync_mod.queue_depth(session)
        by_priority = session.execute(
            select(
                Election.sync_priority,
                func.count(Election.election_id),
                func.count(Election.election_id).filter(Election.sync_complete.is_(True)),
            ).group_by(Election.sync_priority).order_by(Election.sync_priority.asc())
        ).all()
        cache_count = session.scalar(select(func.count(IrevRawCache.cache_id))) or 0
        last_cache = session.scalar(
            select(func.max(IrevRawCache.fetched_at))
        )

    return jsonify(
        {
            "queue": depth,
            "by_priority": [
                {"priority": p, "total": total, "complete": complete}
                for p, total, complete in by_priority
            ],
            "cache": {
                "rows": cache_count,
                "last_fetched_at": last_cache.isoformat() if last_cache else None,
            },
        }
    )
