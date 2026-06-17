"""POST_DEPLOY script: seed/refresh dashboard auth users.

Upsert by email — creates missing users and updates name/role/password for
existing ones, so changing a password here and redeploying takes effect.
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
        "password_hash": "$2b$12$Bbs68.caSBebuh.LMkVueeEtgoCRpNLparPylzFkvKbYBzcA/wNOK",
    },
    {
        "email": "ekitigov@elections.innoedgetech.com",
        "name": "EkitiGov",
        "role": "viewer",
        "password_hash": "$2b$12$.pRPeF8PjK1mIgGiV8iWdeyqJU8FE7Q4KV1mw/VKOw7nlwvAJGkZ6",
    },
]


def main() -> None:
    db_url = os.environ["DATABASE_URL"]
    init_engine(db_url)

    with session_scope() as session:
        for u in USERS:
            existing = session.scalar(select(User).where(User.email == u["email"]))
            if existing:
                existing.name = u["name"]
                existing.role = u["role"]
                existing.password_hash = u["password_hash"]
                existing.is_active = True
                print(f"  updated {u['email']} (role={u['role']})")
            else:
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
