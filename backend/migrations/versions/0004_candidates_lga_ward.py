"""candidates: add lga_id + ward_id for per-LGA / per-ward keyed races

Revision ID: 0004_candidates_lga_ward
Revises: 0003_materialized_views
Create Date: 2026-05-15

LG Chairman + Councillor races run one election per LGA / ward, but our
schema keeps a single Election row per (cycle, election_type, state_id).
The candidates table therefore needs lga_id + ward_id so multiple APC/PDP
candidates can coexist under the same Election row, scoped to their area.

Unique constraint relaxes to (election_id, party_id, COALESCE(lga_id, 0),
COALESCE(ward_id, 0)) so federal/gubernatorial races (no lga/ward) keep
the original semantics.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_candidates_lga_ward"
down_revision: str | None = "0003_materialized_views"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_candidate_election_party", "candidates", type_="unique")
    op.add_column(
        "candidates",
        sa.Column("lga_id", sa.BigInteger(), sa.ForeignKey("lgas.lga_id"), nullable=True),
    )
    op.add_column(
        "candidates",
        sa.Column("ward_id", sa.BigInteger(), sa.ForeignKey("wards.ward_id"), nullable=True),
    )
    # Postgres-only: partial unique indexes per cardinality bucket so nulls
    # don't collapse into one row.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_candidate_election_party_lga_ward
        ON candidates (
          election_id,
          party_id,
          COALESCE(lga_id, 0),
          COALESCE(ward_id, 0)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_candidate_election_party_lga_ward")
    op.drop_column("candidates", "ward_id")
    op.drop_column("candidates", "lga_id")
    op.create_unique_constraint(
        "uq_candidate_election_party", "candidates", ["election_id", "party_id"]
    )
