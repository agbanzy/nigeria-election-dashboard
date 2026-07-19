"""Auth API — login endpoint called by NextAuth credentials provider."""

from __future__ import annotations

from datetime import UTC, datetime

import bcrypt
import click
from flask import Blueprint, jsonify, request
from sqlalchemy import select, update

from app.db import session_scope
from app.models import User
from app.ratelimit import limiter

bp = Blueprint("auth", __name__)


@bp.post("/api/auth/login")
@limiter.limit("10 per minute; 100 per hour")
def login() -> tuple:
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email and password required"}), 400

    with session_scope() as session:
        user = session.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
        if not user:
            return jsonify({"error": "invalid credentials"}), 401

        if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            return jsonify({"error": "invalid credentials"}), 401

        session.execute(
            update(User)
            .where(User.user_id == user.user_id)
            .values(last_login_at=datetime.now(UTC))
        )

        return jsonify(
            {
                "id": str(user.user_id),
                "email": user.email,
                "name": user.name,
                "role": user.role,
            }
        ), 200


@bp.cli.command("create-user")
@click.argument("email")
@click.argument("name")
@click.option("--role", default="viewer", help="admin or viewer")
@click.password_option()
def create_user(email: str, name: str, role: str, password: str) -> None:
    """Create a new dashboard user.

    Usage: flask auth create-user EMAIL NAME [--role admin]
    """
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with session_scope() as session:
        user = User(email=email.lower(), password_hash=pw_hash, name=name, role=role)
        session.add(user)
    click.echo(f"Created user {email} (role={role})")
