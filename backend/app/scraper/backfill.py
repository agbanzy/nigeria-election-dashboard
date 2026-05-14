"""One-shot historical crawl of the IReV proxy.

Usage:
    python -m app.scraper.backfill --cycles 2023,2020 --types presidential,governorship

Iterates every state × election_type. For types whose `ELECTION_TYPE_IDS` value is
None, logs a warning and skips (re-run once Phase B discovers those IDs).
"""

from __future__ import annotations

import argparse
import logging
from datetime import date

from sqlalchemy import select

from app.config import Config
from app.db import init_engine, session_scope
from app.models import State
from app.scraper.discovery import discover_elections_for_state
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
    parser.add_argument("--cycles", default="2023,2020", help="comma-separated years")
    parser.add_argument(
        "--types",
        default="lg_chairman,councillor",
        help="comma-separated election types (see app.scraper.election_types)",
    )
    parser.add_argument("--states", default="", help="comma-separated state_ids; empty = all")
    args = parser.parse_args()

    cfg = Config.from_env()
    init_engine(cfg.database_url)
    logging.basicConfig(level=getattr(logging, cfg.log_level.upper(), logging.INFO))

    cycles = [int(c) for c in args.cycles.split(",") if c.strip()]
    types = [t.strip() for t in args.types.split(",") if t.strip()]
    state_filter = {int(s) for s in args.states.split(",") if s.strip()}

    client = IrevClient(cfg.irev_api_base, cfg.irev_api_key)

    with session_scope() as session:
        ensure_source(session, BACKFILL_SOURCE_NAME)
        all_states = list(session.scalars(select(State)))
        if state_filter:
            all_states = [s for s in all_states if s.state_id in state_filter]

    for cycle in cycles:
        for etype in types:
            if not ELECTION_TYPE_IDS.get(etype):
                log.warning("skipping type=%s — IReV ID not yet discovered", etype)
                continue
            for st in all_states:
                _backfill_one(client, cfg, state_id=st.state_id, election_type=etype, cycle=cycle)


def _backfill_one(
    client: IrevClient, cfg: Config, *, state_id: int, election_type: str, cycle: int
) -> None:
    with session_scope() as session:
        try:
            elections = discover_elections_for_state(
                client, state_id=state_id, election_type=election_type, year=cycle
            )
            for raw in elections:
                irev_id = raw.get("_id") or raw.get("election_id")
                if not irev_id:
                    continue
                date_str = (raw.get("election_date") or "")[:10]
                edate = None
                try:
                    edate = date.fromisoformat(date_str) if date_str else None
                except ValueError:
                    edate = None
                elec = ensure_election(
                    session,
                    cycle=cycle,
                    election_type=election_type,
                    state_id=state_id,
                    irev_election_id=str(irev_id),
                    election_date=edate,
                    status="historical",
                )
                count = scrape_lga_structure(
                    client, session, election=elec, state_id=state_id
                )
                log_phase(
                    session,
                    phase="backfill",
                    state_id=state_id,
                    election_id=elec.election_id,
                    status="ok",
                    message=f"lgas={count}",
                )
        except Exception as exc:  # noqa: BLE001 — log and continue with next election
            log.exception("backfill failed for state=%s type=%s cycle=%s", state_id, election_type, cycle)
            log_phase(
                session,
                phase="backfill",
                state_id=state_id,
                election_id=None,
                status="error",
                message=str(exc),
            )


if __name__ == "__main__":
    main()
