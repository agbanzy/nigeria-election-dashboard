"""Refresh materialized views after an importer load or on a nightly schedule.

Phase D will populate the actual MV definitions. Until then, this is a no-op
that returns the list of MVs the system *expects* to exist.
"""

from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy import text

from app.db import session_scope

log = logging.getLogger(__name__)

EXPECTED_MVS: tuple[str, ...] = (
    "mv_turnout_by_state_cycle",
    "mv_enp",
    "mv_swing",
    "mv_competitiveness",
)


def refresh_materialized_views(mvs: Iterable[str] = EXPECTED_MVS, *, concurrent: bool = True) -> dict[str, str]:
    out: dict[str, str] = {}
    for mv in mvs:
        try:
            with session_scope() as session:
                stmt = f"REFRESH MATERIALIZED VIEW{' CONCURRENTLY' if concurrent else ''} {mv}"
                session.execute(text(stmt))
                out[mv] = "ok"
        except Exception as exc:  # noqa: BLE001 — MVs may not exist yet in Phase A/B
            log.info("skipping MV %s: %s", mv, exc)
            out[mv] = f"skipped: {exc}"
    return out
