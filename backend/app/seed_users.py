"""POST_DEPLOY script: seed/refresh dashboard auth users.

Reads the SEED_USERS env var — a JSON array of
{"email", "name", "role", "password_hash"} objects, where password_hash is a
bcrypt hash (never a plaintext password, and never committed to the repo).
Set it as an encrypted env var on the DO app; when unset the script is a
no-op so deploys don't depend on it.

Generate a hash:
    python -c "import bcrypt, getpass; print(bcrypt.hashpw(getpass.getpass().encode(), bcrypt.gensalt()).decode())"

Upserts by email — creates missing users and updates name/role/password for
existing ones, so rotating a credential is: update SEED_USERS, redeploy.
Run: python -m app.seed_users
"""

from __future__ import annotations

import json
import os

from sqlalchemy import select

from app.db import init_engine, session_scope
from app.models import User

REQUIRED_KEYS = frozenset({"email", "name", "role", "password_hash"})


def load_users() -> list[dict[str, str]]:
    raw = os.environ.get("SEED_USERS", "").strip()
    if not raw:
        return []
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise SystemExit("SEED_USERS must be a JSON array")
    users: list[dict[str, str]] = []
    for item in parsed:
        if not isinstance(item, dict) or REQUIRED_KEYS - item.keys():
            raise SystemExit(f"SEED_USERS entries need keys {sorted(REQUIRED_KEYS)}")
        user = {key: str(item[key]) for key in REQUIRED_KEYS}
        if not user["password_hash"].startswith("$2"):
            raise SystemExit(f"SEED_USERS: {user['email']} password_hash is not a bcrypt hash")
        users.append(user)
    return users


def main() -> None:
    users = load_users()
    if not users:
        print("SEED_USERS not set — nothing to seed.")
        return

    init_engine(os.environ["DATABASE_URL"])

    with session_scope() as session:
        for u in users:
            email = u["email"].lower()
            existing = session.scalar(select(User).where(User.email == email))
            if existing:
                existing.name = u["name"]
                existing.role = u["role"]
                existing.password_hash = u["password_hash"]
                existing.is_active = True
                print(f"  updated {email} (role={u['role']})")
            else:
                session.add(
                    User(
                        email=email,
                        name=u["name"],
                        role=u["role"],
                        password_hash=u["password_hash"],
                        is_active=True,
                    )
                )
                print(f"  created {email} (role={u['role']})")

    print("seed_users done.")


if __name__ == "__main__":
    main()
