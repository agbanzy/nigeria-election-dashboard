"""Party code normalization across cycles.

The `parties` table has a `(code, active_from)` composite unique constraint
so that historical reuse of acronyms is preserved with provenance.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Party

log = logging.getLogger(__name__)


# Map historical codes that have changed meaning. Each entry maps
# (raw_code, cycle) → canonical Party.code to look up (with active_from window).
# Phase B+ will load this from a committed CSV; Phase A inlines the obvious cases.
HISTORICAL_MAPPING: dict[tuple[str, int], str] = {
    # Pre-2013 merger: APC was formed from CPC + ACN + ANPP + part of APGA
    ("CPC", 2011): "CPC",  # original CPC, kept distinct
    ("ACN", 2011): "ACN",
    ("ANPP", 2011): "ANPP",
}


def resolve_party(
    session: Session, *, code: str, cycle: int, autocreate: bool = False
) -> Party | None:
    canonical = HISTORICAL_MAPPING.get((code.upper(), cycle), code.upper())
    stmt = (
        select(Party)
        .where(Party.code == canonical)
        .where((Party.active_from.is_(None)) | (Party.active_from <= cycle))
        .where((Party.active_to.is_(None)) | (Party.active_to >= cycle))
        .order_by(Party.active_from.desc().nullslast())
    )
    party = session.scalar(stmt)
    if party:
        return party
    if autocreate:
        party = Party(code=canonical, name=canonical, active_from=cycle)
        session.add(party)
        session.flush()
        return party
    return None


def find_unmapped(session: Session, codes: Iterable[tuple[str, int]]) -> list[str]:
    out: list[str] = []
    for code, cycle in codes:
        if resolve_party(session, code=code, cycle=cycle) is None:
            out.append(f"{code}@{cycle}")
    return out
