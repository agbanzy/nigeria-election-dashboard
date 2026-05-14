"""GET /api/calendar/next, /api/calendar — drives the countdown widget."""

from __future__ import annotations

from flask import Blueprint, jsonify
from sqlalchemy import select

from app.db import session_scope
from app.models import ElectionCalendar, State
from app.scraper.calendar import seconds_until, upcoming_events
from app.scraper.election_types import LABELS

bp = Blueprint("calendar", __name__, url_prefix="/api/calendar")


@bp.get("/next")
def next_election():
    with session_scope() as session:
        events = upcoming_events(session, limit=1)
        if not events:
            return jsonify(None)
        evt = events[0]
        state = None
        if evt.state_id:
            state = session.scalar(select(State).where(State.state_id == evt.state_id))
        return jsonify(_serialize(evt, state, include_seconds=True))


@bp.get("")
def list_calendar():
    with session_scope() as session:
        events = upcoming_events(session, limit=50)
        by_state = {s.state_id: s for s in session.scalars(select(State))}
        return jsonify(
            [
                _serialize(e, by_state.get(e.state_id) if e.state_id else None)
                for e in events
            ]
        )


def _serialize(
    evt: ElectionCalendar, state: State | None, *, include_seconds: bool = False
) -> dict:
    out = {
        "id": evt.calendar_id,
        "election_date": evt.election_date.isoformat() if evt.election_date else None,
        "election_type": evt.election_type,
        "election_type_label": LABELS.get(evt.election_type, evt.election_type),
        "state_id": evt.state_id,
        "state_code": state.code if state else None,
        "state_name": state.name if state else None,
        "status": evt.status,
        "notes": evt.notes,
    }
    if include_seconds:
        out["seconds_until"] = seconds_until(evt)
    return out
