"""GET /api/states, /api/states/<code>, /api/states/<code>/lgas — geography lookups."""

from __future__ import annotations

from flask import Blueprint, abort, jsonify
from sqlalchemy import select

from app.db import session_scope
from app.models import Lga, State, Ward

bp = Blueprint("states", __name__, url_prefix="/api/states")


@bp.get("")
def list_states():
    with session_scope() as session:
        rows = session.scalars(select(State).order_by(State.name))
        return jsonify(
            [
                {
                    "state_id": s.state_id,
                    "code": s.code,
                    "name": s.name,
                    "zone": s.zone,
                }
                for s in rows
            ]
        )


@bp.get("/<code>")
def get_state(code: str):
    with session_scope() as session:
        state = session.scalar(select(State).where(State.code == code.upper()))
        if state is None:
            abort(404)
        return jsonify(
            {
                "state_id": state.state_id,
                "code": state.code,
                "name": state.name,
                "zone": state.zone,
            }
        )


@bp.get("/<code>/lgas")
def list_lgas(code: str):
    with session_scope() as session:
        state = session.scalar(select(State).where(State.code == code.upper()))
        if state is None:
            abort(404)
        rows = session.scalars(
            select(Lga).where(Lga.state_id == state.state_id).order_by(Lga.name)
        )
        return jsonify(
            [
                {
                    "lga_id": lga.lga_id,
                    "name": lga.name,
                    "kind": lga.lga_kind,
                    "irev_lga_id": lga.irev_lga_id,
                }
                for lga in rows
            ]
        )


@bp.get("/lgas/<int:lga_id>/wards")
def list_wards(lga_id: int):
    with session_scope() as session:
        rows = session.scalars(
            select(Ward).where(Ward.lga_id == lga_id).order_by(Ward.name)
        )
        return jsonify(
            [
                {"ward_id": w.ward_id, "name": w.name, "irev_ward_id": w.irev_ward_id}
                for w in rows
            ]
        )
