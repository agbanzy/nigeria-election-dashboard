"""election_results: add missing FK indexes on lga_id and party_id

Revision ID: 0008_result_indexes
Revises: 0007_api_clients
Create Date: 2026-07-19

Postgres does not auto-index foreign keys. `election_results.lga_id` and
`party_id` are filtered/grouped by the analysis + standings endpoints but had
no standalone index (only the composite ix_results_election_party led with
election_id, so a party-only or lga-only predicate couldn't use it). Adds two
btree indexes. Pure performance — no data or behaviour change.

NOTE: on a large populated table, prefer CREATE INDEX CONCURRENTLY (outside a
transaction) to avoid a write lock. The table is still small here; if it has
grown, run the two indexes manually with CONCURRENTLY before deploying and make
this migration a no-op.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008_result_indexes"
down_revision: str | None = "0007_api_clients"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_results_lga", "election_results", ["lga_id"])
    op.create_index("ix_results_party", "election_results", ["party_id"])


def downgrade() -> None:
    op.drop_index("ix_results_party", table_name="election_results")
    op.drop_index("ix_results_lga", table_name="election_results")
