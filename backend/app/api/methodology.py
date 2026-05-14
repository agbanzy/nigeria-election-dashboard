"""GET /api/methodology — sources, ingestion timestamps, gap disclosure, stat definitions.

This page is critical for credibility: every aggregation the dashboard renders
should link back here. Phase B populates the gap list as historical data lands.
"""

from __future__ import annotations

from flask import Blueprint, jsonify
from sqlalchemy import select

from app.db import session_scope
from app.models import IngestionSource

bp = Blueprint("methodology", __name__, url_prefix="/api/methodology")


_STATISTICAL_DEFINITIONS: list[dict] = [
    {
        "key": "turnout",
        "name": "Turnout",
        "formula": "accredited / registered",
        "description": (
            "Fraction of registered voters who were accredited at polling units. "
            "Reported per state and election cycle."
        ),
    },
    {
        "key": "margin",
        "name": "Margin of victory",
        "formula": "(winner_votes - runner_up_votes) / total_valid_votes",
        "description": "Lead of the winning candidate over the runner-up, as a fraction of total valid votes.",
    },
    {
        "key": "enp",
        "name": "Effective Number of Parties (ENP)",
        "formula": "1 / sum(share_i^2)",
        "description": (
            "Laakso-Taagepera index. ENP=1 means a single party took all votes; "
            "ENP=N means N parties evenly split the vote."
        ),
        "reference": "Laakso & Taagepera, Comparative Political Studies (1979).",
    },
    {
        "key": "swing",
        "name": "Swing",
        "formula": "share_t - share_(t-1)",
        "description": "Change in a party's vote share between two consecutive cycles in the same state and election type.",
    },
    {
        "key": "competitiveness",
        "name": "Competitiveness index",
        "formula": "(1 - margin) * turnout * min(ENP/3, 1)",
        "description": (
            "Composite [0, 1] index that penalizes lopsided races, low turnout, "
            "and uncompetitive party systems."
        ),
        "reference": "Adapted from Cox (1997) and Blais & Lago (2009).",
    },
]


_KNOWN_GAPS: list[dict] = [
    {
        "scope": "2015 State HoA",
        "coverage": "~6 states complete; rest partial or missing",
        "reason": "No national clean dataset; per-state PDFs of varying quality.",
    },
    {
        "scope": "2019 State HoA",
        "coverage": "~80% of LGAs available",
        "reason": "INEC published per-state, mixed format.",
    },
    {
        "scope": "2015 + 2019 LG / Area Council",
        "coverage": "Spotty per-state only",
        "reason": "No national source; some states never published.",
    },
    {
        "scope": "PU-level pre-2023",
        "coverage": "Best-effort via OCR of EC8A scans",
        "reason": "IReV only became authoritative in 2023.",
    },
]


@bp.get("")
def methodology():
    with session_scope() as session:
        sources = session.scalars(select(IngestionSource).order_by(IngestionSource.ingested_at.desc()))
        return jsonify(
            {
                "statistical_definitions": _STATISTICAL_DEFINITIONS,
                "known_gaps": _KNOWN_GAPS,
                "sources": [
                    {
                        "name": s.name,
                        "url": s.url,
                        "license": s.license,
                        "notes": s.notes,
                        "ingested_at": s.ingested_at.isoformat() if s.ingested_at else None,
                    }
                    for s in sources
                ],
                "takedown_contact": "agbane6@gmail.com",
            }
        )
