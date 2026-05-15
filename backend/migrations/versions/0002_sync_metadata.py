"""sync metadata: track per-election sync state + raw response cache

Revision ID: 0002_sync_metadata
Revises: 0001_initial
Create Date: 2026-05-15
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002_sync_metadata"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "elections",
        sa.Column("headers_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "elections",
        sa.Column("structure_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "elections",
        sa.Column("results_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("elections", sa.Column("expected_pus", sa.Integer(), nullable=True))
    op.add_column("elections", sa.Column("uploaded_pus", sa.Integer(), nullable=True))
    op.add_column(
        "elections",
        sa.Column("sync_complete", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    # 1=live, 2=preflight, 3=recent (last 18 months), 5=historical, 9=ignore
    op.add_column(
        "elections",
        sa.Column(
            "sync_priority",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("5"),
        ),
    )
    op.create_index(
        "ix_elections_sync_queue",
        "elections",
        ["sync_complete", "sync_priority"],
    )

    op.create_table(
        "irev_raw_cache",
        sa.Column("cache_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("url_hash", sa.CHAR(64), nullable=False, unique=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("body", JSONB(), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_irev_cache_fetched", "irev_raw_cache", ["fetched_at"])


def downgrade() -> None:
    op.drop_index("ix_irev_cache_fetched", table_name="irev_raw_cache")
    op.drop_table("irev_raw_cache")
    op.drop_index("ix_elections_sync_queue", table_name="elections")
    op.drop_column("elections", "sync_priority")
    op.drop_column("elections", "sync_complete")
    op.drop_column("elections", "uploaded_pus")
    op.drop_column("elections", "expected_pus")
    op.drop_column("elections", "results_synced_at")
    op.drop_column("elections", "structure_synced_at")
    op.drop_column("elections", "headers_synced_at")
