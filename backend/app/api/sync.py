"""GET /api/sync/{status, coverage} — visibility into the sync queue + data coverage."""

from __future__ import annotations

from flask import Blueprint, jsonify
from sqlalchemy import distinct, func, select

from app.db import session_scope
from app.models import (
    Candidate,
    Election,
    ElectionResult,
    IngestionSource,
    IrevRawCache,
    Lga,
    PollingUnit,
    State,
    Ward,
)
from app.scraper import sync as sync_mod
from app.scraper.election_types import LABELS as TYPE_LABELS

bp = Blueprint("sync", __name__, url_prefix="/api/sync")


@bp.get("/status")
def status():
    with session_scope() as session:
        depth = sync_mod.queue_depth(session)
        by_priority = session.execute(
            select(
                Election.sync_priority,
                func.count(Election.election_id),
                func.count(Election.election_id).filter(Election.sync_complete.is_(True)),
            )
            .group_by(Election.sync_priority)
            .order_by(Election.sync_priority.asc())
        ).all()
        cache_count = session.scalar(select(func.count(IrevRawCache.cache_id))) or 0
        last_cache = session.scalar(select(func.max(IrevRawCache.fetched_at)))

    return jsonify(
        {
            "queue": depth,
            "by_priority": [
                {"priority": p, "total": total, "complete": complete}
                for p, total, complete in by_priority
            ],
            "cache": {
                "rows": cache_count,
                "last_fetched_at": last_cache.isoformat() if last_cache else None,
            },
        }
    )


@bp.get("/coverage")
def coverage():
    """Comprehensive sync-coverage report.

    Computes % coverage along every dimension we care about: states ingested,
    election headers, structure (LGA/ward) sync, stats sync, PU-level votes,
    candidates loaded, per-cycle/per-type buckets with curated data.

    Used by the /live page to drive a real-time coverage matrix.
    """
    with session_scope() as session:
        # ─── totals ─────────────────────────────────────────────────────
        total_states = session.scalar(select(func.count(State.state_id))) or 0
        total_lgas = session.scalar(select(func.count(Lga.lga_id))) or 0
        total_wards = session.scalar(select(func.count(Ward.ward_id))) or 0
        total_pus = session.scalar(select(func.count(PollingUnit.pu_id))) or 0
        total_elections = session.scalar(select(func.count(Election.election_id))) or 0

        # ─── elections by sync stage ────────────────────────────────────
        elections_headers = session.scalar(
            select(func.count(Election.election_id)).where(
                Election.headers_synced_at.is_not(None)
            )
        ) or 0
        elections_structure = session.scalar(
            select(func.count(Election.election_id)).where(
                Election.structure_synced_at.is_not(None)
            )
        ) or 0
        elections_stats = session.scalar(
            select(func.count(Election.election_id)).where(
                Election.results_synced_at.is_not(None)
            )
        ) or 0
        elections_complete = session.scalar(
            select(func.count(Election.election_id)).where(
                Election.sync_complete.is_(True)
            )
        ) or 0

        # ─── elections with vote data (any aggregation) ─────────────────
        elections_with_votes = session.scalar(
            select(func.count(distinct(ElectionResult.election_id)))
        ) or 0

        # PU-level votes specifically
        elections_with_pu_votes = session.scalar(
            select(func.count(distinct(ElectionResult.election_id))).where(
                ElectionResult.aggregation == "pu"
            )
        ) or 0

        # ─── candidates ─────────────────────────────────────────────────
        candidates_total = session.scalar(select(func.count(Candidate.candidate_id))) or 0
        elections_with_candidates = session.scalar(
            select(func.count(distinct(Candidate.election_id)))
        ) or 0

        # ─── per-cycle coverage ──────────────────────────────────────────
        per_cycle = session.execute(
            select(
                Election.cycle,
                func.count(Election.election_id),
                func.count(distinct(ElectionResult.election_id)),
            )
            .outerjoin(
                ElectionResult, ElectionResult.election_id == Election.election_id
            )
            .group_by(Election.cycle)
            .order_by(Election.cycle.desc())
        ).all()

        # ─── per-type coverage ───────────────────────────────────────────
        per_type = session.execute(
            select(
                Election.election_type,
                func.count(Election.election_id),
                func.count(distinct(ElectionResult.election_id)),
            )
            .outerjoin(
                ElectionResult, ElectionResult.election_id == Election.election_id
            )
            .group_by(Election.election_type)
        ).all()

        # ─── per-state coverage (does the state appear in any election_results?) ─
        states_with_data = session.scalar(
            select(func.count(distinct(State.state_id)))
            .join(ElectionResult, ElectionResult.state_id == State.state_id)
        ) or 0

        # ─── cache / sources ─────────────────────────────────────────────
        cache_rows = session.scalar(select(func.count(IrevRawCache.cache_id))) or 0
        source_count = session.scalar(select(func.count(IngestionSource.source_id))) or 0

    def pct(num: int, denom: int) -> float:
        return round(num / denom, 4) if denom else 0.0

    return jsonify(
        {
            "geography": {
                "states_total": total_states,
                "states_with_data": states_with_data,
                "states_pct": pct(states_with_data, total_states),
                "lgas_total": total_lgas,
                "wards_total": total_wards,
                "polling_units_total": total_pus,
            },
            "elections": {
                "total": total_elections,
                "headers_synced": elections_headers,
                "structure_synced": elections_structure,
                "stats_synced": elections_stats,
                "with_votes": elections_with_votes,
                "with_pu_votes": elections_with_pu_votes,
                "with_candidates": elections_with_candidates,
                "complete": elections_complete,
                "headers_pct": pct(elections_headers, total_elections),
                "structure_pct": pct(elections_structure, total_elections),
                "stats_pct": pct(elections_stats, total_elections),
                "votes_pct": pct(elections_with_votes, total_elections),
                "pu_votes_pct": pct(elections_with_pu_votes, total_elections),
                "candidates_pct": pct(elections_with_candidates, total_elections),
                "complete_pct": pct(elections_complete, total_elections),
            },
            "candidates": {"total": candidates_total},
            "cache": {"rows": cache_rows, "ingestion_sources": source_count},
            "per_cycle": [
                {
                    "cycle": c,
                    "elections": int(n),
                    "with_data": int(d),
                    "pct": pct(int(d), int(n)),
                }
                for c, n, d in per_cycle
            ],
            "per_type": [
                {
                    "type": t,
                    "label": TYPE_LABELS.get(t, t),
                    "elections": int(n),
                    "with_data": int(d),
                    "pct": pct(int(d), int(n)),
                }
                for t, n, d in per_type
            ],
        }
    )
