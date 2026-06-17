"""One-time POST_DEPLOY script: seed dashboard auth users.

Idempotent — skips users that already exist by email.
Run: python -m app.seed_users
"""

from __future__ import annotations

import os

from sqlalchemy import select

from app.db import init_engine, session_scope
from app.models import User


USERS = [
    {
        "email": "godwin@innoedgetech.com",
        "name": "Godwin Agbane",
        "role": "admin",
        "password_hash": "$2b$12$46Ow9PHrTkXn6oQ0dbuWUOAtIFxRR8yVrzjJbFJeETCyc/3VA8dRC",
    },
    {
        "email": "ekitigov@elections.innoedgetech.com",
        "name": "EkitiGov",
        "role": "viewer",
        "password_hash": "$2b$12$gx8aEv86urRyoELuP.rPVuNc5lpXcnuBFZpJw3icl.x/Dm9l80Pki",
    },
]


def main() -> None:
    db_url = os.environ["DATABASE_URL"]
    init_engine(db_url)

    with session_scope() as session:
        for u in USERS:
            existing = session.scalar(select(User).where(User.email == u["email"]))
            if existing:
                print(f"  skip {u['email']} (already exists)")
                continue
            session.add(
                User(
                    email=u["email"],
                    name=u["name"],
                    role=u["role"],
                    password_hash=u["password_hash"],
                    is_active=True,
                )
            )
            print(f"  created {u['email']} (role={u['role']})")

    print("seed_users done.")


if __name__ == "__main__":
    main()
