"""Add api_clients table — apply-and-approve free API access.

Revision ID: 0007_api_clients
Revises: 0006_users
Create Date: 2026-07-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_api_clients"
down_revision: str | None = "0006_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_clients",
        sa.Column("client_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("use_case", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("application_ref", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("client_id"),
        sa.UniqueConstraint("email", name="uq_api_clients_email"),
        sa.UniqueConstraint("api_key", name="uq_api_clients_api_key"),
        sa.UniqueConstraint("application_ref", name="uq_api_clients_application_ref"),
    )
    op.create_index("ix_api_clients_api_key", "api_clients", ["api_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_api_clients_api_key", table_name="api_clients")
    op.drop_table("api_clients")
