"""Background scraper daemon.

Wake policy is calendar-driven: idle 24h unless an election is live (2-min cycle)
or within the configured pre-flight window (5-min cycle).

Runs as the `worker` component on DO App Platform — separate process from `web`
so scraper stalls never affect API latency.

Usage:
    python -m app.scraper.daemon
"""

from __future__ import annotations

import logging
import signal
import sys
import time
from datetime import datetime, timezone

from app.config import Config
from app.db import init_engine, session_scope
from app.scraper.calendar import decide_mode
from app.scraper.discovery import discover_elections_for_state
from app.scraper.election_types import ELECTION_TYPE_IDS
from app.scraper.irev_client import IrevClient
from app.scraper.phases import (
    LIVE_SOURCE_NAME,
    ensure_election,
    ensure_source,
    log_phase,
    scrape_lga_structure,
)

log = logging.getLogger(__name__)

_running = True


def _handle_signal(signum: int, frame) -> None:  # type: ignore[no-untyped-def]
    global _running
    _running = False
    log.info("signal %s received, shutting down", signum)


def main() -> int:
    cfg = Config.from_env()
    init_engine(cfg.database_url)
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log.info("scraper daemon starting (enabled=%s)", cfg.scraper_enabled)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if not cfg.scraper_enabled:
        log.warning("SCRAPER_ENABLED=false — sleeping indefinitely")
        while _running:
            time.sleep(60)
        return 0

    client = IrevClient(cfg.irev_api_base, cfg.irev_api_key)
    with session_scope() as session:
        ensure_source(session, LIVE_SOURCE_NAME)

    while _running:
        try:
            with session_scope() as session:
                decision = decide_mode(
                    session,
                    live_interval=cfg.scraper_interval_live_seconds,
                    preflight_interval=cfg.scraper_interval_preflight_seconds,
                    idle_interval=cfg.scraper_interval_idle_seconds,
                    preflight_window_hours=cfg.scraper_preflight_window_hours,
                )
            log.info(
                "wake decision: mode=%s interval=%ss states=%s next=%s",
                decision.mode,
                decision.interval_seconds,
                sorted(decision.state_ids),
                decision.next_event.election_date if decision.next_event else None,
            )
            if decision.mode != "idle" and decision.state_ids:
                _run_cycle(client, state_ids=decision.state_ids)
        except Exception:  # noqa: BLE001 — never let scraper thread die on a transient error
            log.exception("scraper loop iteration failed")
            decision_interval = cfg.scraper_interval_idle_seconds

        _interruptible_sleep(decision.interval_seconds)
    return 0


def _run_cycle(client: IrevClient, *, state_ids: frozenset[int]) -> None:
    types = [t for t, v in ELECTION_TYPE_IDS.items() if v]
    for state_id in sorted(state_ids):
        for etype in types:
            try:
                with session_scope() as session:
                    elections = discover_elections_for_state(
                        client, state_id=state_id, election_type=etype
                    )
                    for raw in elections:
                        irev_id = raw.get("_id") or raw.get("election_id")
                        if not irev_id:
                            continue
                        elec = ensure_election(
                            session,
                            cycle=_extract_cycle(raw),
                            election_type=etype,
                            state_id=state_id,
                            irev_election_id=str(irev_id),
                            election_date=None,
                            status="live",
                        )
                        scrape_lga_structure(
                            client, session, election=elec, state_id=state_id
                        )
                        log_phase(
                            session,
                            phase="live",
                            state_id=state_id,
                            election_id=elec.election_id,
                            status="ok",
                        )
            except Exception:  # noqa: BLE001
                log.exception("cycle phase failed state=%s type=%s", state_id, etype)


def _extract_cycle(raw: dict[str, object]) -> int:
    date_str = str(raw.get("election_date") or "")[:4]
    try:
        return int(date_str)
    except ValueError:
        return datetime.now(timezone.utc).year


def _interruptible_sleep(seconds: int) -> None:
    end = time.monotonic() + seconds
    while _running and time.monotonic() < end:
        time.sleep(min(1.0, end - time.monotonic()))


if __name__ == "__main__":
    sys.exit(main())
