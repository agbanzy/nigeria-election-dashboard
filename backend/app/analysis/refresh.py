"""Refresh materialized views.

Called by the importer after each load and by the daemon nightly.

CONCURRENTLY refresh requires a UNIQUE index on every MV — set up by
migration 0003. First-time refresh of a freshly-created MV must run
non-concurrently (Postgres rejects CONCURRENT on an empty MV with no data).
We try CONCURRENTLY first and fall back on the specific error.
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


def refresh_materialized_views(
    mvs: Iterable[str] = EXPECTED_MVS,
    *,
    concurrent: bool = True,
) -> dict[str, str]:
    """Refresh each MV. Returns {mv_name: 'ok'|'skipped: <reason>'}."""
    out: dict[str, str] = {}
    for mv in mvs:
        out[mv] = _refresh_one(mv, concurrent=concurrent)
    return out


def _refresh_one(mv: str, *, concurrent: bool) -> str:
    # Try concurrent first; on failure (typically "cannot refresh ... has not been
    # populated") fall back to a blocking refresh.
    for is_concurrent in (concurrent, False) if concurrent else (False,):
        stmt = f"REFRESH MATERIALIZED VIEW{' CONCURRENTLY' if is_concurrent else ''} {mv}"
        try:
            with session_scope() as session:
                session.execute(text(stmt))
            log.info("refresh: %s ok (concurrent=%s)", mv, is_concurrent)
            return "ok"
        except Exception as exc:  # noqa: BLE001
            log.info("refresh: %s failed (concurrent=%s): %s", mv, is_concurrent, exc)
            if is_concurrent:
                continue
            return f"skipped: {exc}"
    return "skipped: exhausted retries"
