"""Candidate CSV loader.

Schema:
  state_code, election_type, cycle, lga_name?, ward_name?, party_code,
  candidate_name, is_incumbent

For races scoped to an LGA (lg_chairman) or ward (councillor), set lga_name
/ ward_name. The loader resolves them to lga_id / ward_id and creates rows
if missing. The Election row itself is one per (cycle, type, state) — the
LGA/ward scoping lives on the candidate row.

Idempotent on (election_id, party_id, lga_id, ward_id) via the partial
unique index from migration 0004.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.db import session_scope
from app.importer.normalizers import resolve_party
from app.importer.schemas import ImportSummary
from app.models import Candidate, IngestionSource, Lga, State, Ward
from app.scraper.phases import ensure_election

log = logging.getLogger(__name__)


def load_candidates_csv(
    *,
    filepath: Path,
    source_name: str,
    source_license: str = "public",
    source_url: str = "",
) -> ImportSummary:
    with filepath.open() as fh:
        rows = list(csv.DictReader(fh))

    rows_in = len(rows)
    imported = 0
    skipped = 0
    errors: list[str] = []
    unmapped: set[str] = set()
    elections_touched: set[int] = set()

    with session_scope() as session:
        source = _ensure_source(session, source_name, source_license, source_url)

        for i, raw in enumerate(rows, start=2):
            try:
                cycle = int(raw["cycle"])
                etype = raw["election_type"].strip()
                state_code = raw["state_code"].strip().upper()
                party_code = raw["party_code"].strip().upper()
                full_name = raw["candidate_name"].strip()
                is_incumbent = str(raw.get("is_incumbent", "")).lower() in ("1", "true", "yes")
                lga_name = (raw.get("lga_name") or "").strip() or None
                ward_name = (raw.get("ward_name") or "").strip() or None
            except (KeyError, ValueError) as exc:
                errors.append(f"row {i}: bad column ({exc})")
                skipped += 1
                continue

            if not full_name:
                skipped += 1
                continue

            state = session.scalar(select(State).where(State.code == state_code))
            if state is None and state_code != "NG":
                errors.append(f"row {i}: unknown state_code={state_code}")
                skipped += 1
                continue

            party = resolve_party(session, code=party_code, cycle=cycle, autocreate=True)
            if party is None:
                unmapped.add(party_code)
                skipped += 1
                continue

            election = ensure_election(
                session,
                cycle=cycle,
                election_type=etype,
                state_id=state.state_id if state else None,
                irev_election_id=None,
                election_date=None,
                status="historical",
            )
            elections_touched.add(election.election_id)

            lga = _lookup_or_create_lga(session, state, lga_name)
            ward = _lookup_or_create_ward(session, lga, ward_name)

            # Upsert by (election_id, party_id, lga_id, ward_id)
            existing = session.scalar(
                select(Candidate).where(
                    Candidate.election_id == election.election_id,
                    Candidate.party_id == party.party_id,
                    _eq_or_null(Candidate.lga_id, lga.lga_id if lga else None),
                    _eq_or_null(Candidate.ward_id, ward.ward_id if ward else None),
                )
            )
            if existing:
                # Update name + incumbency if changed
                changed = False
                if existing.full_name != full_name:
                    existing.full_name = full_name
                    changed = True
                if existing.is_incumbent != is_incumbent:
                    existing.is_incumbent = is_incumbent
                    changed = True
                if changed:
                    imported += 1
                else:
                    skipped += 1
                continue

            session.add(
                Candidate(
                    election_id=election.election_id,
                    party_id=party.party_id,
                    full_name=full_name,
                    is_incumbent=is_incumbent,
                    lga_id=lga.lga_id if lga else None,
                    ward_id=ward.ward_id if ward else None,
                )
            )
            imported += 1

    return ImportSummary(
        rows_in=rows_in,
        rows_imported=imported,
        rows_skipped=skipped,
        elections_touched=len(elections_touched),
        unmapped_parties=sorted(unmapped),
        errors=errors[:50],
    )


def _eq_or_null(col: Any, value: int | None):  # type: ignore[no-untyped-def]
    return col == value if value is not None else col.is_(None)


def _lookup_or_create_lga(session: Any, state: State | None, name: str | None) -> Lga | None:
    if not name or state is None:
        return None
    lga = session.scalar(
        select(Lga).where(Lga.state_id == state.state_id, Lga.name == name)
    )
    if lga is None:
        lga = Lga(state_id=state.state_id, name=name)
        session.add(lga)
        session.flush()
    return lga


def _lookup_or_create_ward(session: Any, lga: Lga | None, name: str | None) -> Ward | None:
    if not name or lga is None:
        return None
    ward = session.scalar(
        select(Ward).where(Ward.lga_id == lga.lga_id, Ward.name == name)
    )
    if ward is None:
        ward = Ward(lga_id=lga.lga_id, name=name)
        session.add(ward)
        session.flush()
    return ward


def _ensure_source(session: Any, name: str, license_: str, url: str) -> IngestionSource:
    src = session.scalar(select(IngestionSource).where(IngestionSource.name == name))
    if src:
        return src
    src = IngestionSource(name=name, url=url or None, license=license_)
    session.add(src)
    session.flush()
    return src
