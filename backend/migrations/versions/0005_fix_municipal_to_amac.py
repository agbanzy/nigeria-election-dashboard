"""One-shot cleanup: FCT 2026 results were loaded with LGA name 'Municipal'
(from legacy SQLite) instead of 'AMAC' (the INEC official name).

Drops the old ingestion_sources + their election_results, and the orphan
'Municipal' LGA in FC state. The next POST_DEPLOY seed-historical run
will re-import the (corrected) CSVs under v2 source names.

Revision ID: 0005_fix_municipal_to_amac
Revises: 0004_candidates_lga_ward
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0005_fix_municipal_to_amac"
down_revision: str | None = "0004_candidates_lga_ward"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop rows ingested under the old source names so the renamed v2 sources
    # in seed_historical land cleanly. Idempotent — if the rows don't exist,
    # nothing happens.
    op.execute(
        """
        DELETE FROM election_results
        WHERE source_id IN (
          SELECT source_id FROM ingestion_sources
          WHERE name IN (
            'inec_irev_2026_fct_chairman',
            'inec_irev_2026_fct_councillor',
            'inec_2026_fct_candidates'
          )
        )
        """
    )
    op.execute(
        """
        DELETE FROM candidates
        WHERE election_id IN (
          SELECT election_id FROM elections
          WHERE cycle = 2026 AND election_type IN ('lg_chairman', 'councillor')
            AND state_id = 15
        )
        """
    )
    op.execute(
        """
        DELETE FROM ingestion_sources
        WHERE name IN (
          'inec_irev_2026_fct_chairman',
          'inec_irev_2026_fct_councillor',
          'inec_2026_fct_candidates'
        )
        """
    )
    # Drop the orphan 'Municipal' LGA in FCT (it's a stale alias for AMAC).
    op.execute(
        """
        DELETE FROM lgas
        WHERE state_id = 15 AND name = 'Municipal'
          AND NOT EXISTS (
            SELECT 1 FROM election_results WHERE lga_id = lgas.lga_id
          )
        """
    )


def downgrade() -> None:
    # No-op: data can be re-created by re-running seed_historical.
    pass
