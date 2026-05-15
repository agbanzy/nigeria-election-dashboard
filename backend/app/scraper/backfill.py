"""One-shot historical crawl of the IReV API.

Usage:
    python -m app.scraper.backfill --cycles 2026,2025,2024 --types presidential,governorship

For each election type we fetch the full list ONCE (one API call returns all
elections of that type across every state). Then we filter locally by cycle
and the optional state set. This is dramatically faster than the per-state
discovery pattern: ~7 API calls upfront instead of 37 × 7 = 259.

LGA-structure fetch still costs one API call per election; that's unavoidable.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from typing import Any

from sqlalchemy import select

from app.config import Config
from app.db import init_engine, session_scope
from app.models import State
from app.scraper.election_types import ELECTION_TYPE_IDS
from app.scraper.irev_client import IrevClient
from app.scraper.phases import (
    BACKFILL_SOURCE_NAME,
    ensure_election,
    ensure_source,
    log_phase,
    scrape_lga_structure,
)

log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="IReV historical backfill")
    parser.add_argument("--cycles", default="2026,2025,2024,2023,2022", help="comma-separated years")
    parser.add_argument(
        "--types",
        default="presidential,governorship,senate,reps,state_hoa,lg_chairman,councillor",
        help="comma-separated election types (see app.scraper.election_types)",
    )
    parser.add_argument("--states", default="", help="comma-separated state_ids; empty = all")
    parser.add_argument(
        "--skip-lga-structure",
        action="store_true",
        help="Only fetch + record election headers; skip the LGA/ward structure walk",
    )
    args = parser.parse_args()

    cfg = Config.from_env()
    init_engine(cfg.database_url)
    logging.basicConfig(level=getattr(logging, cfg.log_level.upper(), logging.INFO))

    cycles = {int(c) for c in args.cycles.split(",") if c.strip()}
    types = [t.strip() for t in args.types.split(",") if t.strip()]
    state_filter = {int(s) for s in args.states.split(",") if s.strip()}

    client = IrevClient(cfg.irev_api_base, cfg.irev_api_key)

    with session_scope() as session:
        ensure_source(session, BACKFILL_SOURCE_NAME)
        all_state_ids = {s.state_id for s in session.scalars(select(State))}
    if state_filter:
        target_state_ids = state_filter & all_state_ids
    else:
        target_state_ids = all_state_ids

    for etype in types:
        irev_type_id = ELECTION_TYPE_IDS.get(etype)
        if not irev_type_id:
            log.warning("skipping type=%s — no IReV ID configured", etype)
            continue
        log.info("backfill: fetching all elections of type=%s", etype)
        try:
            raw_list_resp = client.list_elections(election_type_id=irev_type_id)
        except Exception:
            log.exception("backfill: list_elections failed for type=%s", etype)
            continue

        # The API returns {success, data: [...]} or sometimes raw list.
        if isinstance(raw_list_resp, dict):
            elections = raw_list_resp.get("data") or []
        else:
            elections = raw_list_resp or []
        log.info("backfill: type=%s returned %d elections", etype, len(elections))

        matched = 0
        for raw in elections:
            if not isinstance(raw, dict):
                continue
            cycle = _extract_cycle(raw)
            if cycles and cycle not in cycles:
                continue
            state_id_raw = raw.get("state_id")
            # Presidential is national — state_id missing or 0
            elec_state_id: int | None
            if etype == "presidential":
                elec_state_id = None
            elif state_id_raw is None:
                elec_state_id = None
            else:
                try:
                    elec_state_id = int(state_id_raw)
                except (TypeError, ValueError):
                    continue
                if elec_state_id not in target_state_ids:
                    continue
            _persist_election(
                client,
                raw,
                etype=etype,
                cycle=cycle,
                state_id=elec_state_id,
                skip_lga=args.skip_lga_structure,
            )
            matched += 1
        log.info("backfill: type=%s persisted %d elections", etype, matched)


def _extract_cycle(raw: dict[str, Any]) -> int:
    s = str(raw.get("election_date") or "")[:4]
    try:
        return int(s)
    except ValueError:
        return 0


def _persist_election(
    client: IrevClient,
    raw: dict[str, Any],
    *,
    etype: str,
    cycle: int,
    state_id: int | None,
    skip_lga: bool,
) -> None:
    irev_id = raw.get("_id") or raw.get("election_id")
    if not irev_id:
        return
    date_str = (raw.get("election_date") or "")[:10]
    try:
        edate = date.fromisoformat(date_str) if date_str else None
    except ValueError:
        edate = None

    with session_scope() as session:
        try:
            elec = ensure_election(
                session,
                cycle=cycle,
                election_type=etype,
                state_id=state_id,
                irev_election_id=str(irev_id),
                election_date=edate,
                status="historical",
            )
            structure_count = 0
            if not skip_lga and state_id is not None:
                try:
                    structure_count = scrape_lga_structure(
                        client, session, election=elec, state_id=state_id
                    )
                except Exception:
                    log.exception(
                        "backfill: lga structure failed for state=%s elec=%s", state_id, elec.election_id
                    )
            log_phase(
                session,
                phase="backfill",
                state_id=state_id,
                election_id=elec.election_id,
                status="ok",
                message=f"lgas={structure_count}",
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("backfill: persist failed for irev_id=%s", irev_id)
            log_phase(
                session,
                phase="backfill",
                state_id=state_id,
                election_id=None,
                status="error",
                message=str(exc)[:200],
            )


if __name__ == "__main__":
    main()
