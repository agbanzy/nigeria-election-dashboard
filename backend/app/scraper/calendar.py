"""Election calendar — drives both the scraper wake policy and the UI countdown.

The `Mode` returned by `decide_mode()` is consumed by `daemon.py` and exposed via
`/api/calendar/next` for the frontend countdown.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ElectionCalendar


Mode = Literal["live", "preflight", "idle"]


@dataclass(frozen=True)
class WakeDecision:
    mode: Mode
    interval_seconds: int
    state_ids: frozenset[int]
    next_event: ElectionCalendar | None


def upcoming_events(session: Session, *, limit: int = 10) -> list[ElectionCalendar]:
    now = datetime.now(timezone.utc).date()
    stmt = (
        select(ElectionCalendar)
        .where(ElectionCalendar.election_date >= now)
        .where(ElectionCalendar.status.in_(("scheduled", "live")))
        .order_by(ElectionCalendar.election_date.asc())
        .limit(limit)
    )
    return list(session.scalars(stmt))


def next_event(session: Session) -> ElectionCalendar | None:
    events = upcoming_events(session, limit=1)
    return events[0] if events else None


def live_events(session: Session) -> list[ElectionCalendar]:
    stmt = select(ElectionCalendar).where(ElectionCalendar.status == "live")
    return list(session.scalars(stmt))


def decide_mode(
    session: Session,
    *,
    now: datetime | None = None,
    live_interval: int = 120,
    preflight_interval: int = 300,
    idle_interval: int = 86_400,
    preflight_window_hours: int = 6,
) -> WakeDecision:
    now = now or datetime.now(timezone.utc)
    live = live_events(session)
    if live:
        state_ids = frozenset(e.state_id for e in live if e.state_id is not None)
        return WakeDecision(
            mode="live",
            interval_seconds=live_interval,
            state_ids=state_ids,
            next_event=live[0],
        )

    upcoming = next_event(session)
    if upcoming is not None:
        delta = datetime.combine(upcoming.election_date, datetime.min.time(), tzinfo=timezone.utc) - now
        if 0 <= delta.total_seconds() <= preflight_window_hours * 3600:
            state_ids = frozenset({upcoming.state_id}) if upcoming.state_id else frozenset()
            return WakeDecision(
                mode="preflight",
                interval_seconds=preflight_interval,
                state_ids=state_ids,
                next_event=upcoming,
            )
    return WakeDecision(
        mode="idle",
        interval_seconds=idle_interval,
        state_ids=frozenset(),
        next_event=upcoming,
    )


def seconds_until(event: ElectionCalendar | None, *, now: datetime | None = None) -> int | None:
    if event is None:
        return None
    now = now or datetime.now(timezone.utc)
    target = datetime.combine(event.election_date, datetime.min.time(), tzinfo=timezone.utc)
    return max(0, int((target - now).total_seconds()))
