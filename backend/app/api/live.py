"""GET /api/live/events — server-sent events stream.

Phase A delivers a minimal SSE endpoint that emits heartbeats and any scraper
status broadcast by the worker. The actual broadcaster is a TODO for Phase B —
it requires either Postgres LISTEN/NOTIFY or a Redis pub/sub channel.

Until the broadcaster lands, this stream only emits heartbeats every 15s so
the frontend's `EventSource` connection stays alive.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime

from flask import Blueprint, Response

bp = Blueprint("live", __name__, url_prefix="/api/live")


@bp.get("/events")
def events():
    def gen():
        yield f"event: connected\ndata: {json.dumps({'ts': datetime.now(UTC).isoformat()})}\n\n"
        while True:
            time.sleep(15)
            yield f"event: heartbeat\ndata: {json.dumps({'ts': datetime.now(UTC).isoformat()})}\n\n"

    return Response(gen(), mimetype="text/event-stream")
