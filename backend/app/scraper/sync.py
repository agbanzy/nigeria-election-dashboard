"""Incremental sync engine.

Four idempotent operations driven by the daemon:

  1. discover_election_headers() — list each election type ONCE (≈7 calls),
     upsert election headers. Sets headers_synced_at.
  2. sync_election_structure(election) — pull LGAs + wards. Sets
     structure_synced_at. Skipped if already done within freshness window.
  3. sync_election_stats(election) — pull /result/stats. Updates
     expected_pus / uploaded_pus. Marks sync_complete on completion.
  4. sync_election_pus(election) — walk /pus?ward=<id> per ward, parse the
     `votes` array (present for 2026+ data), upsert PollingUnit rows and
     ElectionResult rows with aggregation='pu'. One ward per tick keeps
     it polite. This is the PU → ward → LGA → state → national pipeline.

The daemon calls `tick(client, max_api_calls)` to drain the queue at a polite
rate. Historical elections (sync_priority=5) tick at idle pace; live ones
(priority=1) get full sync every cycle.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.importer.normalizers import resolve_party
from app.models import (
    Election,
    ElectionResult,
    Lga,
    PollingUnit,
    State,
    Ward,
)
from app.scraper.election_types import (
    ELECTION_TYPE_IDS,
)
from app.scraper.irev_client import IrevClient
from app.scraper.phases import (
    BACKFILL_SOURCE_NAME,
    LIVE_SOURCE_NAME,
    ensure_election,
    ensure_source,
    log_phase,
    scrape_lga_structure,
    upsert_polling_unit,
)

log = logging.getLogger(__name__)


STRUCTURE_FRESHNESS = timedelta(days=30)   # historical elections: re-sync structure monthly tops
RESULTS_FRESHNESS_LIVE = timedelta(minutes=2)
RESULTS_FRESHNESS_RECENT = timedelta(hours=6)
RESULTS_FRESHNESS_HISTORICAL = timedelta(days=7)


# ────────────────────────────────────────────────────────────────────────────
# Op 1: header discovery
# ────────────────────────────────────────────────────────────────────────────

def discover_election_headers(session: Session, client: IrevClient) -> dict[str, int]:
    """One API call per election type. Upserts election headers + priority.

    Total cost: 7 API calls. Returns {type: rows_touched}.
    """
    ensure_source(session, BACKFILL_SOURCE_NAME)
    valid_state_ids = {s.state_id for s in session.scalars(select(State))}
    touched: dict[str, int] = {}
    today = date.today()

    for etype, irev_type_id in ELECTION_TYPE_IDS.items():
        if not irev_type_id:
            continue
        try:
            resp = client.list_elections(election_type_id=irev_type_id)
        except Exception:
            log.exception("sync: list_elections failed for %s", etype)
            continue
        elections = resp.get("data") if isinstance(resp, dict) else resp
        if not elections:
            touched[etype] = 0
            continue

        n = 0
        for raw in elections:
            if not isinstance(raw, dict):
                continue
            cycle = _extract_cycle(raw)
            if cycle == 0:
                continue
            edate = _extract_date(raw)
            irev_id = str(raw.get("_id") or raw.get("election_id") or "")
            if not irev_id:
                continue

            # Presidential is national; for everything else, attach to state.
            state_id: int | None
            if etype == "presidential":
                state_id = None
            else:
                sid = raw.get("state_id")
                if sid is None or sid == 0:
                    state_id = None
                else:
                    try:
                        sid = int(sid)
                    except (TypeError, ValueError):
                        continue
                    if sid not in valid_state_ids:
                        continue
                    state_id = sid

            elec = ensure_election(
                session,
                cycle=cycle,
                election_type=etype,
                state_id=state_id,
                irev_election_id=irev_id,
                election_date=edate,
                status="historical",
            )
            elec.headers_synced_at = datetime.now(UTC)
            elec.sync_priority = _compute_priority(edate, today)
            n += 1
        touched[etype] = n
        log.info("sync: discovered headers for %s -> %d rows", etype, n)

    return touched


def _extract_cycle(raw: dict[str, Any]) -> int:
    s = str(raw.get("election_date") or "")[:4]
    try:
        return int(s)
    except ValueError:
        return 0


def _extract_date(raw: dict[str, Any]) -> date | None:
    s = str(raw.get("election_date") or "")[:10]
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _compute_priority(election_date: date | None, today: date) -> int:
    """1=live (election_date today), 2=preflight (<7d), 3=recent (<18mo), 5=historical."""
    if election_date is None:
        return 5
    delta = (election_date - today).days
    if -1 <= delta <= 1:
        return 1
    if 0 <= delta <= 7:
        return 2
    if -540 <= delta <= 0:
        return 3
    return 5


# ────────────────────────────────────────────────────────────────────────────
# Op 2: structure sync
# ────────────────────────────────────────────────────────────────────────────

def sync_election_structure(
    session: Session, client: IrevClient, election: Election, *, force: bool = False
) -> bool:
    """Walk LGAs + wards for one election. Idempotent. Returns True if work done."""
    if election.state_id is None:
        # Presidential national row — no per-state structure to walk.
        election.structure_synced_at = datetime.now(UTC)
        return False
    now = datetime.now(UTC)
    if (
        not force
        and election.structure_synced_at
        and now - election.structure_synced_at < STRUCTURE_FRESHNESS
    ):
        return False
    try:
        count = scrape_lga_structure(
            client, session, election=election, state_id=election.state_id
        )
        election.structure_synced_at = now
        log_phase(
            session,
            phase="structure",
            state_id=election.state_id,
            election_id=election.election_id,
            status="ok",
            message=f"lgas={count}",
        )
        return True
    except Exception as exc:  # noqa: BLE001 — surface and continue
        log_phase(
            session,
            phase="structure",
            state_id=election.state_id,
            election_id=election.election_id,
            status="error",
            message=str(exc)[:200],
        )
        log.exception(
            "sync: structure failed election_id=%s state=%s", election.election_id, election.state_id
        )
        return False


# ────────────────────────────────────────────────────────────────────────────
# Op 3: results sync (stats only at this phase; full PU walk is Phase C work)
# ────────────────────────────────────────────────────────────────────────────

def sync_election_stats(
    session: Session, client: IrevClient, election: Election
) -> bool:
    """Hit /result/stats. Cheap (1 call). Updates expected_pus / uploaded_pus.

    Marks `sync_complete = True` when uploaded == expected. Returns True if API
    was hit.
    """
    if not election.irev_election_id:
        return False
    try:
        resp = client.election_stats(election.irev_election_id)
    except Exception:
        log.exception("sync: stats failed for election_id=%s", election.election_id)
        return False

    data = resp.get("data") if isinstance(resp, dict) else resp
    if not isinstance(data, dict):
        # Some elections return an empty stats blob — treat as 0/0.
        data = {}

    expected = _coerce_int(data.get("expected"))
    uploaded = _coerce_int(data.get("documents") or data.get("uploaded"))
    election.expected_pus = expected
    election.uploaded_pus = uploaded
    election.results_synced_at = datetime.now(UTC)
    if expected is not None and uploaded is not None and expected > 0 and uploaded >= expected:
        election.sync_complete = True
    log_phase(
        session,
        phase="stats",
        state_id=election.state_id,
        election_id=election.election_id,
        status="ok",
        message=f"expected={expected} uploaded={uploaded}",
    )
    return True


def _coerce_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# ────────────────────────────────────────────────────────────────────────────
# Queue selection + tick
# ────────────────────────────────────────────────────────────────────────────

def select_next_targets(session: Session, *, limit: int = 5) -> list[Election]:
    """Pick the next N elections to advance.

    Order:
      1. sync_complete = False
      2. ASC by sync_priority (1=live first)
      3. NULLS FIRST on results_synced_at (untouched first), else ASC (oldest sync first)
    """
    stmt = (
        select(Election)
        .where(Election.sync_complete.is_(False))
        .order_by(
            Election.sync_priority.asc(),
            Election.results_synced_at.asc().nullsfirst(),
        )
        .limit(limit)
    )
    return list(session.scalars(stmt))


def tick(session: Session, client: IrevClient, *, max_api_calls: int) -> dict[str, int]:
    """Advance the sync queue, doing at most `max_api_calls` IReV calls."""
    calls = 0
    counters = {
        "structure": 0,
        "stats": 0,
        "pu_wards": 0,
        "pu_results": 0,
        "elections_touched": 0,
    }
    targets = select_next_targets(session, limit=max_api_calls)
    for elec in targets:
        if calls >= max_api_calls:
            break

        if (
            elec.structure_synced_at is None
            and elec.state_id is not None
            and sync_election_structure(session, client, elec)
        ):
            counters["structure"] += 1
            calls += 1

        if calls >= max_api_calls:
            break

        if (
            elec.irev_election_id
            and not elec.sync_complete
            and sync_election_stats(session, client, elec)
        ):
            counters["stats"] += 1
            calls += 1

        # PU walk — only after structure exists, and only when budget remains.
        if (
            calls < max_api_calls
            and elec.structure_synced_at is not None
            and elec.irev_election_id
            and elec.state_id is not None
        ):
            n_wards, n_results = sync_election_pus(
                session, client, elec, max_wards=max(1, max_api_calls - calls)
            )
            counters["pu_wards"] += n_wards
            counters["pu_results"] += n_results
            calls += n_wards

        counters["elections_touched"] += 1

    counters["api_calls"] = calls
    return counters


# ────────────────────────────────────────────────────────────────────────────
# Op 4: per-PU walk → ElectionResult(aggregation='pu')
# ────────────────────────────────────────────────────────────────────────────

PARTY_VOTE_CEILING = 100_000  # sanity guard


def sync_election_pus(
    session: Session,
    client: IrevClient,
    election: Election,
    *,
    max_wards: int = 5,
) -> tuple[int, int]:
    """Walk wards under this election's state, fetch /pus?ward=<id>, persist
    PU-level vote rows. Skips wards already covered.

    Returns (wards_processed, rows_inserted).
    """
    if not election.irev_election_id or election.state_id is None:
        return 0, 0

    stmt = (
        select(Ward)
        .join(Lga, Lga.lga_id == Ward.lga_id)
        .where(Lga.state_id == election.state_id, Ward.irev_ward_id.isnot(None))
        .limit(max_wards * 4)
    )
    candidates = list(session.scalars(stmt))
    if not candidates:
        return 0, 0

    source = ensure_source(session, LIVE_SOURCE_NAME)
    processed = 0
    rows_inserted = 0
    for ward in candidates:
        if processed >= max_wards:
            break
        already = session.scalar(
            select(func.count(ElectionResult.result_id))
            .join(PollingUnit, PollingUnit.pu_id == ElectionResult.pu_id)
            .where(
                ElectionResult.election_id == election.election_id,
                PollingUnit.ward_id == ward.ward_id,
            )
        ) or 0
        if already > 0:
            continue
        try:
            resp = client.pus_for_ward(election.irev_election_id, str(ward.irev_ward_id))
            n = _persist_ward_pu_results(session, election, ward, resp, source_id=source.source_id)
            rows_inserted += n
            log_phase(
                session,
                phase="pu",
                state_id=election.state_id,
                election_id=election.election_id,
                status="ok",
                message=f"ward={ward.ward_id} rows={n}",
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("sync: pu fetch failed e=%s w=%s", election.election_id, ward.ward_id)
            log_phase(
                session,
                phase="pu",
                state_id=election.state_id,
                election_id=election.election_id,
                status="error",
                message=str(exc)[:200],
            )
        processed += 1
    return processed, rows_inserted


def _persist_ward_pu_results(
    session: Session,
    election: Election,
    ward: Ward,
    resp: Any,
    *,
    source_id: int,
) -> int:
    data = resp.get("data") if isinstance(resp, dict) else resp
    if not isinstance(data, list):
        return 0
    inserted = 0
    for pu_raw in data:
        if not isinstance(pu_raw, dict):
            continue
        pu = upsert_polling_unit(
            session,
            ward,
            irev_pu_id=_as_int_safe(pu_raw.get("polling_unit_id") or pu_raw.get("_id")),
            pu_code=pu_raw.get("pu_code") or pu_raw.get("code"),
            name=pu_raw.get("name"),
        )
        votes_field = pu_raw.get("votes")
        if isinstance(votes_field, str):
            try:
                votes_field = json.loads(votes_field)
            except json.JSONDecodeError:
                votes_field = None
        if not isinstance(votes_field, list):
            continue
        for v in votes_field:
            if not isinstance(v, dict):
                continue
            code = (v.get("party_code") or "").upper().strip()
            try:
                count = int(v.get("vote") or 0)
            except (TypeError, ValueError):
                continue
            if not code or count < 0 or count > PARTY_VOTE_CEILING:
                continue
            party = resolve_party(session, code=code, cycle=election.cycle, autocreate=True)
            if party is None:
                continue
            session.add(
                ElectionResult(
                    election_id=election.election_id,
                    pu_id=pu.pu_id,
                    state_id=election.state_id,
                    aggregation="pu",
                    party_id=party.party_id,
                    votes=count,
                    source_id=source_id,
                )
            )
            inserted += 1
    if inserted:
        session.flush()
    return inserted


def _as_int_safe(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def queue_depth(session: Session) -> dict[str, int]:
    """Visibility helper — counts by sync state."""
    total = session.scalar(select(func.count(Election.election_id))) or 0
    complete = session.scalar(
        select(func.count(Election.election_id)).where(Election.sync_complete.is_(True))
    ) or 0
    no_structure = session.scalar(
        select(func.count(Election.election_id)).where(
            Election.structure_synced_at.is_(None), Election.state_id.is_not(None)
        )
    ) or 0
    no_stats = session.scalar(
        select(func.count(Election.election_id)).where(Election.results_synced_at.is_(None))
    ) or 0
    return {
        "total": total,
        "complete": complete,
        "pending_structure": no_structure,
        "pending_stats": no_stats,
        "pending_total": total - complete,
    }
