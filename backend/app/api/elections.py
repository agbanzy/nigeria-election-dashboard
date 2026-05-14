"""GET /api/elections — list with filters; /api/elections/<id> — detail + standings."""

from __future__ import annotations

from collections import defaultdict

from flask import Blueprint, abort, jsonify, request
from sqlalchemy import select

from app.analysis.competitiveness import competitiveness_index
from app.analysis.descriptive import margin_of_victory, turnout
from app.analysis.enp import effective_number_of_parties
from app.db import session_scope
from app.models import Candidate, Election, ElectionResult, Party, State
from app.scraper.election_types import LABELS

bp = Blueprint("elections", __name__, url_prefix="/api/elections")


@bp.get("")
def list_elections():
    state_code = request.args.get("state")
    cycle = request.args.get("cycle", type=int)
    etype = request.args.get("type")
    with session_scope() as session:
        stmt = select(Election)
        if state_code:
            stmt = stmt.join(State, State.state_id == Election.state_id).where(
                State.code == state_code.upper()
            )
        if cycle:
            stmt = stmt.where(Election.cycle == cycle)
        if etype:
            stmt = stmt.where(Election.election_type == etype)
        stmt = stmt.order_by(Election.election_date.desc().nullslast(), Election.cycle.desc())
        return jsonify([_serialize_election(e) for e in session.scalars(stmt)])


@bp.get("/<int:election_id>")
def get_election(election_id: int):
    with session_scope() as session:
        election = session.get(Election, election_id)
        if election is None:
            abort(404)
        return jsonify(_serialize_election(election))


@bp.get("/<int:election_id>/standings")
def get_standings(election_id: int):
    with session_scope() as session:
        election = session.get(Election, election_id)
        if election is None:
            abort(404)

        candidates_by_party = {
            c.party_id: c
            for c in session.scalars(
                select(Candidate).where(Candidate.election_id == election_id)
            )
        }

        rows = session.execute(
            select(
                ElectionResult.party_id,
                Party.code,
                Party.name,
                Party.color_hex,
            )
            .join(Party, Party.party_id == ElectionResult.party_id)
            .where(ElectionResult.election_id == election_id)
        ).all()

        votes_by_party: dict[int, int] = defaultdict(int)
        accredited_total = 0
        registered_total = 0
        for r in session.scalars(
            select(ElectionResult).where(ElectionResult.election_id == election_id)
        ):
            votes_by_party[r.party_id] += r.votes
            if r.accredited_voters:
                accredited_total += r.accredited_voters
            if r.registered_voters:
                registered_total += r.registered_voters

        standings = []
        for party_id, code, name, color in rows:
            v = votes_by_party.get(party_id, 0)
            cand = candidates_by_party.get(party_id)
            standings.append(
                {
                    "party_id": party_id,
                    "party_code": code,
                    "party_name": name,
                    "party_color": color,
                    "candidate": cand.full_name if cand else None,
                    "is_incumbent": cand.is_incumbent if cand else False,
                    "votes": v,
                }
            )
        standings.sort(key=lambda x: x["votes"], reverse=True)
        total = sum(votes_by_party.values())
        for s in standings:
            s["share"] = (s["votes"] / total) if total else 0.0

        return jsonify(
            {
                "election": _serialize_election(election),
                "standings": standings,
                "stats": {
                    "total_votes": total,
                    "accredited": accredited_total or None,
                    "registered": registered_total or None,
                    "turnout": turnout(accredited_total or None, registered_total or None),
                    "margin": margin_of_victory(votes_by_party),
                    "enp": effective_number_of_parties(votes_by_party),
                    "competitiveness": competitiveness_index(
                        votes_by_party=votes_by_party,
                        accredited=accredited_total or None,
                        registered=registered_total or None,
                    ),
                },
            }
        )


def _serialize_election(e: Election) -> dict:
    return {
        "election_id": e.election_id,
        "cycle": e.cycle,
        "election_type": e.election_type,
        "election_type_label": LABELS.get(e.election_type, e.election_type),
        "state_id": e.state_id,
        "election_date": e.election_date.isoformat() if e.election_date else None,
        "status": e.status,
        "irev_election_id": e.irev_election_id,
    }
