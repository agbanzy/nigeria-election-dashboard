"""Developer API access — apply-and-approve free API keys.

The dashboard and its data are free for everyone. Programmatic API access is
also free, but by application: POST /api/developer/apply creates a pending
request; an admin approves it (via /api/admin/api-clients or the
`flask developer` CLI); the applicant retrieves their key with the
application_ref returned at apply time. The ref is the retrieval secret — it
is shown once and never re-issued, so a duplicate apply for an existing email
returns 409 without leaking anything.
"""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime

import click
from flask import Blueprint, jsonify, request
from sqlalchemy import select

from app.db import session_scope
from app.models import ApiClient

bp = Blueprint("developer", __name__, url_prefix="/api/developer")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_FIELD = 500


def _new_ref() -> str:
    return secrets.token_urlsafe(24)


def _new_key() -> str:
    return "ned_" + secrets.token_hex(24)


@bp.post("/apply")
def apply():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip().lower()
    use_case = (body.get("use_case") or "").strip()

    if not name or not email or not use_case:
        return jsonify({"error": "name, email and use_case are required"}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"error": "invalid email"}), 400
    if max(len(name), len(email), len(use_case)) > MAX_FIELD:
        return jsonify({"error": f"fields are limited to {MAX_FIELD} characters"}), 400

    with session_scope() as session:
        existing = session.scalar(select(ApiClient).where(ApiClient.email == email))
        if existing:
            return (
                jsonify(
                    {
                        "error": "an application for this email already exists",
                        "status": existing.status,
                    }
                ),
                409,
            )
        ref = _new_ref()
        session.add(ApiClient(name=name, email=email, use_case=use_case, application_ref=ref))

    return (
        jsonify(
            {
                "ok": True,
                "status": "pending",
                "application_ref": ref,
                "message": (
                    "Application received. Keep your application_ref — it is the "
                    "only way to retrieve your key once approved."
                ),
            }
        ),
        201,
    )


@bp.post("/status")
def status():
    body = request.get_json(silent=True) or {}
    ref = (body.get("application_ref") or "").strip()
    if not ref:
        return jsonify({"error": "application_ref is required"}), 400

    with session_scope() as session:
        client = session.scalar(select(ApiClient).where(ApiClient.application_ref == ref))
        if not client:
            return jsonify({"error": "unknown application_ref"}), 404
        out: dict[str, str | None] = {"status": client.status, "name": client.name}
        if client.status == "approved":
            out["api_key"] = client.api_key
        return jsonify(out), 200


def _decide(session, email: str, new_status: str) -> ApiClient | None:
    client = session.scalar(select(ApiClient).where(ApiClient.email == email.lower()))
    if not client:
        return None
    client.status = new_status
    client.decided_at = datetime.now(UTC)
    if new_status == "approved" and not client.api_key:
        client.api_key = _new_key()
    if new_status in ("rejected", "revoked"):
        client.api_key = None
    return client


@bp.cli.command("list")
def cli_list() -> None:
    """List API access applications."""
    with session_scope() as session:
        clients = session.scalars(select(ApiClient).order_by(ApiClient.created_at)).all()
        for c in clients:
            click.echo(f"{c.status:9} {c.email:40} {c.name} — {c.use_case[:60]}")
        if not clients:
            click.echo("no applications yet.")


@bp.cli.command("approve")
@click.argument("email")
def cli_approve(email: str) -> None:
    """Approve an application and issue a key."""
    with session_scope() as session:
        client = _decide(session, email, "approved")
        click.echo(f"approved {email}" if client else f"no application for {email}")


@bp.cli.command("reject")
@click.argument("email")
def cli_reject(email: str) -> None:
    """Reject an application."""
    with session_scope() as session:
        client = _decide(session, email, "rejected")
        click.echo(f"rejected {email}" if client else f"no application for {email}")


@bp.cli.command("revoke")
@click.argument("email")
def cli_revoke(email: str) -> None:
    """Revoke an approved client's key."""
    with session_scope() as session:
        client = _decide(session, email, "revoked")
        click.echo(f"revoked {email}" if client else f"no application for {email}")
