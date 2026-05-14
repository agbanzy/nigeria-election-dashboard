"""GET /api/candidates — filterable by election or party."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from app.db import session_scope
from app.models import Candidate, Party

bp = Blueprint("candidates", __name__, url_prefix="/api/candidates")


@bp.get("")
def list_candidates():
    election_id = request.args.get("election", type=int)
    party_code = request.args.get("party")
    with session_scope() as session:
        stmt = select(Candidate, Party).join(Party, Party.party_id == Candidate.party_id)
        if election_id:
            stmt = stmt.where(Candidate.election_id == election_id)
        if party_code:
            stmt = stmt.where(Party.code == party_code.upper())
        out = []
        for c, p in session.execute(stmt).all():
            out.append(
                {
                    "candidate_id": c.candidate_id,
                    "election_id": c.election_id,
                    "party_code": p.code,
                    "party_name": p.name,
                    "party_color": p.color_hex,
                    "full_name": c.full_name,
                    "is_incumbent": c.is_incumbent,
                }
            )
        return jsonify(out)
