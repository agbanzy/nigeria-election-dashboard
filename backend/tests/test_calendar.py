"""Tests for the scraper wake-mode logic."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.integration


def test_decide_mode_idle_with_no_calendar(db_engine):
    from app.db import session_scope
    from app.scraper.calendar import decide_mode

    with session_scope() as session:
        decision = decide_mode(session)
    assert decision.mode == "idle"
    assert decision.interval_seconds >= 60 * 60  # at least 1h


def test_decide_mode_preflight_within_window(db_engine):
    from app.db import session_scope
    from app.models import ElectionCalendar
    from app.scraper.calendar import decide_mode

    today = date.today()
    with session_scope() as session:
        session.add(
            ElectionCalendar(
                election_date=today, election_type="presidential", status="scheduled"
            )
        )

    fixed_now = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc) - timedelta(hours=2)
    with session_scope() as session:
        decision = decide_mode(session, now=fixed_now)
    assert decision.mode == "preflight"


def test_decide_mode_live_overrides_calendar(db_engine):
    from app.db import session_scope
    from app.models import ElectionCalendar
    from app.scraper.calendar import decide_mode

    with session_scope() as session:
        session.add(
            ElectionCalendar(
                election_date=date.today(), election_type="presidential", status="live", state_id=15
            )
        )

    with session_scope() as session:
        decision = decide_mode(session)
    assert decision.mode == "live"
    assert 15 in decision.state_ids
