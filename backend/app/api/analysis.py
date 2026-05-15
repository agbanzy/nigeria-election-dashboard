"""GET /api/analysis/{turnout,enp,swing,competitiveness,heatmap,timeline}.

Phase A delivers compute-on-the-fly versions. Phase D will swap heavy queries
for materialized views (`mv_turnout`, `mv_enp`, `mv_swing`, `mv_competitiveness`)
without changing the response shape.
"""

from __future__ import annotations

from collections import defaultdict

from flask import Blueprint, jsonify, request
from sqlalchemy import func, select, text as _text

from app.analysis.competitiveness import competitiveness_index
from app.analysis.descriptive import margin_of_victory, turnout
from app.analysis.enp import effective_number_of_parties
from app.analysis.swing import compute_swings
from app.db import session_scope
from app.models import Election, ElectionResult, Party, ScrapeLog, State

bp = Blueprint("analysis", __name__, url_prefix="/api/analysis")


@bp.get("/turnout")
def turnout_by_state():
    cycle = request.args.get("cycle", type=int)
    etype = request.args.get("type")
    with session_scope() as session:
        stmt = (
            select(
                State.code,
                State.name,
                func.sum(ElectionResult.accredited_voters),
                func.sum(ElectionResult.registered_voters),
            )
            .join(State, State.state_id == ElectionResult.state_id)
            .join(Election, Election.election_id == ElectionResult.election_id)
        )
        if cycle:
            stmt = stmt.where(Election.cycle == cycle)
        if etype:
            stmt = stmt.where(Election.election_type == etype)
        stmt = stmt.group_by(State.code, State.name)
        out = []
        for code, name, acc, reg in session.execute(stmt).all():
            out.append(
                {
                    "state_code": code,
                    "state_name": name,
                    "accredited": acc,
                    "registered": reg,
                    "turnout": turnout(acc, reg),
                }
            )
        return jsonify(out)


@bp.get("/enp")
def enp_by_election():
    """Read mv_enp when present; fall back to on-the-fly computation otherwise."""
    cycle = request.args.get("cycle", type=int)
    etype = request.args.get("type")
    with session_scope() as session:
        # Try materialized view first
        try:
            mv_sql = "SELECT election_id, cycle, election_type, state_id, enp, total_votes FROM mv_enp"
            where = []
            params: dict = {}
            if cycle:
                where.append("cycle = :cycle")
                params["cycle"] = cycle
            if etype:
                where.append("election_type = :etype")
                params["etype"] = etype
            if where:
                mv_sql += " WHERE " + " AND ".join(where)
            mv_rows = list(session.execute(_text(mv_sql), params))
            if mv_rows:
                return jsonify(
                    [
                        {
                            "election_id": r[0],
                            "cycle": r[1],
                            "type": r[2],
                            "state_id": r[3],
                            "enp": float(r[4] or 0),
                            "margin": _margin_for(session, r[0]),
                        }
                        for r in mv_rows
                    ]
                )
        except Exception:
            pass  # MV may not exist yet — fall through

        stmt = select(Election)
        if cycle:
            stmt = stmt.where(Election.cycle == cycle)
        if etype:
            stmt = stmt.where(Election.election_type == etype)
        out = []
        for e in session.scalars(stmt):
            votes = _votes_by_party(session, e.election_id)
            out.append(
                {
                    "election_id": e.election_id,
                    "cycle": e.cycle,
                    "type": e.election_type,
                    "state_id": e.state_id,
                    "enp": effective_number_of_parties(votes),
                    "margin": margin_of_victory(votes),
                }
            )
        return jsonify(out)


def _margin_for(session, election_id: int) -> float | None:
    """Lightweight margin lookup for MV-served rows."""
    return margin_of_victory(_votes_by_party(session, election_id))


@bp.get("/swing")
def swing_between_cycles():
    state_code = request.args.get("state")
    etype = request.args.get("type")
    cycle_a = request.args.get("a", type=int)
    cycle_b = request.args.get("b", type=int)
    if not (cycle_a and cycle_b and etype):
        return jsonify({"error": "missing required: a, b, type"}), 400
    with session_scope() as session:
        a_votes = _votes_for(session, cycle=cycle_a, etype=etype, state_code=state_code)
        b_votes = _votes_for(session, cycle=cycle_b, etype=etype, state_code=state_code)
        swings = compute_swings(a_votes, b_votes)
        return jsonify(
            {
                "cycle_a": cycle_a,
                "cycle_b": cycle_b,
                "type": etype,
                "state_code": state_code,
                "swings": [
                    {
                        "party_id": s.party,
                        "share_prior": s.share_prior,
                        "share_current": s.share_current,
                        "delta": s.delta,
                    }
                    for s in swings
                ],
            }
        )


@bp.get("/competitiveness")
def competitiveness():
    cycle = request.args.get("cycle", type=int)
    etype = request.args.get("type")
    with session_scope() as session:
        stmt = select(Election)
        if cycle:
            stmt = stmt.where(Election.cycle == cycle)
        if etype:
            stmt = stmt.where(Election.election_type == etype)
        out = []
        for e in session.scalars(stmt):
            votes = _votes_by_party(session, e.election_id)
            stats = _stats(session, e.election_id)
            out.append(
                {
                    "election_id": e.election_id,
                    "state_id": e.state_id,
                    "cycle": e.cycle,
                    "type": e.election_type,
                    "competitiveness": competitiveness_index(
                        votes_by_party=votes,
                        accredited=stats["accredited"],
                        registered=stats["registered"],
                    ),
                }
            )
        return jsonify(out)


@bp.get("/timeline")
def scrape_timeline():
    limit = min(request.args.get("limit", default=300, type=int), 2000)
    with session_scope() as session:
        rows = session.scalars(
            select(ScrapeLog).order_by(ScrapeLog.created_at.desc()).limit(limit)
        )
        return jsonify(
            [
                {
                    "log_id": r.log_id,
                    "phase": r.phase,
                    "state_id": r.state_id,
                    "election_id": r.election_id,
                    "status": r.status,
                    "message": r.message,
                    "duration_ms": r.duration_ms,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
        )


def _votes_by_party(session, election_id: int) -> dict[int, int]:
    out: dict[int, int] = defaultdict(int)
    for r in session.scalars(
        select(ElectionResult).where(ElectionResult.election_id == election_id)
    ):
        out[r.party_id] += r.votes
    return out


def _stats(session, election_id: int) -> dict:
    acc = 0
    reg = 0
    for r in session.scalars(
        select(ElectionResult).where(ElectionResult.election_id == election_id)
    ):
        acc += r.accredited_voters or 0
        reg += r.registered_voters or 0
    return {"accredited": acc or None, "registered": reg or None}


def _votes_for(session, *, cycle: int, etype: str, state_code: str | None) -> dict[int, int]:
    stmt = (
        select(ElectionResult.party_id, func.sum(ElectionResult.votes))
        .join(Election, Election.election_id == ElectionResult.election_id)
        .where(Election.cycle == cycle, Election.election_type == etype)
        .group_by(ElectionResult.party_id)
    )
    if state_code:
        stmt = stmt.join(State, State.state_id == ElectionResult.state_id).where(
            State.code == state_code.upper()
        )
    return {pid: int(v) for pid, v in session.execute(stmt).all()}
