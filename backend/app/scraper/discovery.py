"""Discover IReV elections for a given state + election type.

Port of legacy `discover_elections()` (election_dashboard.py:322) with
`FCT_STATE_ID = 15` replaced by an explicit `state_id` argument.
"""

from __future__ import annotations

import logging
from typing import Any

from app.scraper.election_types import ELECTION_TYPE_IDS
from app.scraper.irev_client import IrevClient

log = logging.getLogger(__name__)


def discover_elections_for_state(
    client: IrevClient,
    *,
    state_id: int,
    election_type: str,
    year: int | None = None,
) -> list[dict[str, Any]]:
    irev_id = ELECTION_TYPE_IDS.get(election_type)
    if not irev_id:
        log.info("no IReV id for type=%s, skipping discovery", election_type)
        return []

    raw = client.list_elections(election_type_id=irev_id) or []
    out: list[dict[str, Any]] = []
    for elec in raw:
        if not isinstance(elec, dict):
            continue
        if elec.get("state_id") != state_id:
            continue
        if year is not None:
            date_str = (elec.get("election_date") or "").strip()
            if not date_str.startswith(str(year)):
                continue
        out.append(elec)
    log.info(
        "discovered %d elections for state=%s type=%s year=%s",
        len(out),
        state_id,
        election_type,
        year,
    )
    return out
