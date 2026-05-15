"""materialized views: turnout, ENP, swing, competitiveness

Revision ID: 0003_materialized_views
Revises: 0002_sync_metadata
Create Date: 2026-05-15

The views read from `election_results` (aggregated at any level) and are
refreshed by `app.analysis.refresh.refresh_materialized_views()` after each
importer load and nightly via the daemon.

When no curated/PU-level votes have been ingested for an election, the row
simply isn't in the MV. Frontend treats absence as "data not yet available."
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0003_materialized_views"
down_revision: Union[str, None] = "0002_sync_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# turnout per state × cycle × type (where accredited + registered are available)
# ---------------------------------------------------------------------------
TURNOUT_VIEW = """
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_turnout_by_state_cycle AS
SELECT
  e.cycle,
  e.election_type,
  e.state_id,
  SUM(r.votes)::BIGINT             AS total_votes,
  SUM(r.accredited_voters)::BIGINT AS accredited,
  SUM(r.registered_voters)::BIGINT AS registered,
  CASE
    WHEN SUM(r.registered_voters) > 0
      THEN SUM(r.accredited_voters)::FLOAT / SUM(r.registered_voters)
    ELSE NULL
  END AS turnout
FROM elections e
JOIN election_results r USING (election_id)
WHERE r.aggregation IN ('state', 'national')
GROUP BY e.cycle, e.election_type, e.state_id;
"""

# ---------------------------------------------------------------------------
# ENP (Laakso–Taagepera) per election
# ---------------------------------------------------------------------------
ENP_VIEW = """
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_enp AS
WITH party_totals AS (
  SELECT
    r.election_id,
    r.party_id,
    SUM(r.votes)::FLOAT AS party_votes
  FROM election_results r
  WHERE r.aggregation IN ('pu', 'ward', 'lga', 'state', 'national')
  GROUP BY r.election_id, r.party_id
),
election_totals AS (
  SELECT
    election_id,
    SUM(party_votes) AS total_votes
  FROM party_totals
  GROUP BY election_id
),
party_shares AS (
  SELECT
    pt.election_id,
    pt.party_votes / NULLIF(et.total_votes, 0) AS share
  FROM party_totals pt
  JOIN election_totals et USING (election_id)
)
SELECT
  e.election_id,
  e.cycle,
  e.election_type,
  e.state_id,
  COUNT(*)                                                AS party_count,
  et.total_votes::BIGINT                                  AS total_votes,
  CASE
    WHEN SUM(share * share) > 0 THEN 1.0 / SUM(share * share)
    ELSE 0.0
  END                                                     AS enp
FROM elections e
JOIN party_shares ps USING (election_id)
JOIN election_totals et USING (election_id)
GROUP BY e.election_id, e.cycle, e.election_type, e.state_id, et.total_votes;
"""

# ---------------------------------------------------------------------------
# Swing (Δ share between consecutive cycles, same state + type)
# ---------------------------------------------------------------------------
SWING_VIEW = """
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_swing AS
WITH shares AS (
  SELECT
    e.cycle,
    e.election_type,
    e.state_id,
    r.party_id,
    SUM(r.votes)::FLOAT
      / NULLIF(SUM(SUM(r.votes)) OVER (PARTITION BY e.election_id), 0) AS share
  FROM elections e
  JOIN election_results r USING (election_id)
  GROUP BY e.cycle, e.election_type, e.state_id, r.party_id, e.election_id
),
agg AS (
  SELECT cycle, election_type, state_id, party_id,
         AVG(share) AS share
  FROM shares
  GROUP BY cycle, election_type, state_id, party_id
)
SELECT
  cycle,
  election_type,
  state_id,
  party_id,
  share AS current_share,
  LAG(share) OVER (
    PARTITION BY election_type, state_id, party_id
    ORDER BY cycle
  ) AS prior_share,
  share - LAG(share) OVER (
    PARTITION BY election_type, state_id, party_id
    ORDER BY cycle
  ) AS swing
FROM agg;
"""

# ---------------------------------------------------------------------------
# Competitiveness index: (1 - margin) × turnout × min(ENP/3, 1)
# ---------------------------------------------------------------------------
COMPETITIVENESS_VIEW = """
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_competitiveness AS
WITH party_totals AS (
  SELECT r.election_id, r.party_id, SUM(r.votes)::FLOAT AS votes
  FROM election_results r
  GROUP BY r.election_id, r.party_id
),
ranked AS (
  SELECT
    election_id,
    party_id,
    votes,
    ROW_NUMBER() OVER (PARTITION BY election_id ORDER BY votes DESC) AS rk,
    SUM(votes) OVER (PARTITION BY election_id) AS total
  FROM party_totals
),
margin_cte AS (
  SELECT
    election_id,
    (
      MAX(votes) FILTER (WHERE rk = 1)
      - COALESCE(MAX(votes) FILTER (WHERE rk = 2), 0)
    ) / NULLIF(MAX(total), 0) AS margin
  FROM ranked
  GROUP BY election_id
),
turnout_cte AS (
  SELECT
    election_id,
    SUM(accredited_voters)::FLOAT / NULLIF(SUM(registered_voters), 0) AS turnout
  FROM election_results
  GROUP BY election_id
)
SELECT
  e.election_id,
  e.cycle,
  e.election_type,
  e.state_id,
  m.margin,
  t.turnout,
  enp.enp,
  CASE
    WHEN m.margin IS NULL OR t.turnout IS NULL OR enp.enp <= 0 THEN NULL
    ELSE LEAST(1.0, GREATEST(0.0,
      (1.0 - m.margin) * t.turnout * LEAST(1.0, enp.enp / 3.0)
    ))
  END AS competitiveness
FROM elections e
LEFT JOIN margin_cte m USING (election_id)
LEFT JOIN turnout_cte t USING (election_id)
LEFT JOIN mv_enp enp USING (election_id);
"""

INDEXES = [
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_mv_turnout_unique ON mv_turnout_by_state_cycle (cycle, election_type, COALESCE(state_id, -1))",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_mv_enp_unique ON mv_enp (election_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_mv_swing_unique ON mv_swing (cycle, election_type, COALESCE(state_id, -1), party_id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_mv_competitiveness_unique ON mv_competitiveness (election_id)",
]


def upgrade() -> None:
    op.execute(TURNOUT_VIEW)
    op.execute(ENP_VIEW)
    op.execute(SWING_VIEW)
    op.execute(COMPETITIVENESS_VIEW)
    for stmt in INDEXES:
        op.execute(stmt)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_competitiveness")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_swing")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_enp")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_turnout_by_state_cycle")
