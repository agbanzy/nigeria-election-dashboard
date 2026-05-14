"""Generic CSV loader — reads any file conforming to `schemas.ResultRow`.

The CSV header must match the field names exactly (state_code, lga_name, ward_name,
pu_code, party_code, votes, accredited, registered, candidate_name, is_incumbent).

`cycle`, `election_type`, `aggregation` are supplied via CLI flags rather than
columns, since they're constant per file.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Literal

from sqlalchemy import select

from app.db import session_scope
from app.importer.normalizers import resolve_party
from app.importer.schemas import ImportSummary, ResultRow
from app.models import (
    Candidate,
    Election,
    ElectionResult,
    IngestionSource,
    Lga,
    State,
)
from app.scraper.phases import ensure_election

log = logging.getLogger(__name__)

Aggregation = Literal["pu", "ward", "lga", "state", "national"]


def load_csv(
    *,
    filepath: Path,
    cycle: int,
    election_type: str,
    aggregation: Aggregation,
    source_name: str,
    source_license: str,
    source_url: str,
) -> ImportSummary:
    with filepath.open() as fh:
        reader = csv.DictReader(fh)
        raw_rows = list(reader)

    rows_in = len(raw_rows)
    rows_imported = 0
    rows_skipped = 0
    errors: list[str] = []
    unmapped: set[str] = set()
    elections_touched: set[int] = set()

    with session_scope() as session:
        source = session.scalar(select(IngestionSource).where(IngestionSource.name == source_name))
        if source is None:
            source = IngestionSource(
                name=source_name, url=source_url or None, license=source_license
            )
            session.add(source)
            session.flush()

        for i, raw in enumerate(raw_rows, start=2):  # 2 = header + 1
            try:
                row = ResultRow(
                    cycle=cycle,
                    election_type=election_type,
                    aggregation=aggregation,
                    is_incumbent=str(raw.get("is_incumbent", "")).lower() in ("1", "true", "yes"),
                    **{k: v for k, v in raw.items() if k != "is_incumbent"},  # type: ignore[arg-type]
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"row {i}: {exc}")
                rows_skipped += 1
                continue

            state = session.scalar(select(State).where(State.code == row.state_code))
            if state is None:
                errors.append(f"row {i}: unknown state_code={row.state_code}")
                rows_skipped += 1
                continue

            party = resolve_party(session, code=row.party_code, cycle=cycle)
            if party is None:
                unmapped.add(row.party_code)
                rows_skipped += 1
                continue

            election = ensure_election(
                session,
                cycle=cycle,
                election_type=election_type,
                state_id=state.state_id if aggregation != "national" else None,
                irev_election_id=None,
                election_date=None,
                status="historical",
            )
            elections_touched.add(election.election_id)

            lga = None
            if row.lga_name:
                lga = session.scalar(
                    select(Lga).where(
                        Lga.state_id == state.state_id, Lga.name == row.lga_name
                    )
                )
                if lga is None:
                    lga = Lga(state_id=state.state_id, name=row.lga_name)
                    session.add(lga)
                    session.flush()

            if row.candidate_name:
                existing_cand = session.scalar(
                    select(Candidate).where(
                        Candidate.election_id == election.election_id,
                        Candidate.party_id == party.party_id,
                    )
                )
                if existing_cand is None:
                    session.add(
                        Candidate(
                            election_id=election.election_id,
                            party_id=party.party_id,
                            full_name=row.candidate_name,
                            is_incumbent=row.is_incumbent,
                        )
                    )

            session.add(
                ElectionResult(
                    election_id=election.election_id,
                    pu_id=None,
                    lga_id=lga.lga_id if lga else None,
                    state_id=state.state_id if aggregation != "national" else None,
                    aggregation=aggregation,
                    party_id=party.party_id,
                    votes=row.votes,
                    accredited_voters=row.accredited,
                    registered_voters=row.registered,
                    source_id=source.source_id,
                )
            )
            rows_imported += 1

    if elections_touched:
        try:
            from app.analysis.refresh import refresh_materialized_views

            refresh_materialized_views()
        except Exception:  # noqa: BLE001 — MVs may not exist yet
            log.info("MV refresh skipped (likely Phase A/B, no MVs yet)")

    return ImportSummary(
        rows_in=rows_in,
        rows_imported=rows_imported,
        rows_skipped=rows_skipped,
        elections_touched=len(elections_touched),
        unmapped_parties=sorted(unmapped),
        errors=errors[:50],
    )
