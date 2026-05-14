"""initial unified schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "states",
        sa.Column("state_id", sa.SmallInteger(), primary_key=True),
        sa.Column("code", sa.CHAR(2), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("zone", sa.Text(), nullable=False),
    )

    op.create_table(
        "lgas",
        sa.Column("lga_id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "state_id",
            sa.SmallInteger(),
            sa.ForeignKey("states.state_id"),
            nullable=False,
        ),
        sa.Column("irev_lga_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("lga_kind", sa.Text(), nullable=False, server_default=sa.text("'lga'")),
        sa.UniqueConstraint("state_id", "name", name="uq_lga_state_name"),
    )

    op.create_table(
        "wards",
        sa.Column("ward_id", sa.BigInteger(), primary_key=True),
        sa.Column("lga_id", sa.BigInteger(), sa.ForeignKey("lgas.lga_id"), nullable=False),
        sa.Column("irev_ward_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
    )

    op.create_table(
        "polling_units",
        sa.Column("pu_id", sa.BigInteger(), primary_key=True),
        sa.Column("ward_id", sa.BigInteger(), sa.ForeignKey("wards.ward_id"), nullable=False),
        sa.Column("irev_pu_id", sa.BigInteger(), nullable=True),
        sa.Column("pu_code", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("registered_voters", sa.Integer(), nullable=True),
    )

    op.create_table(
        "parties",
        sa.Column("party_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("color_hex", sa.CHAR(7), nullable=True),
        sa.Column("active_from", sa.SmallInteger(), nullable=True),
        sa.Column("active_to", sa.SmallInteger(), nullable=True),
        sa.UniqueConstraint("code", "active_from", name="uq_party_code_from"),
    )

    op.create_table(
        "elections",
        sa.Column("election_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("cycle", sa.SmallInteger(), nullable=False),
        sa.Column("election_type", sa.Text(), nullable=False),
        sa.Column(
            "state_id",
            sa.SmallInteger(),
            sa.ForeignKey("states.state_id"),
            nullable=True,
        ),
        sa.Column("irev_election_id", sa.Text(), nullable=True),
        sa.Column("election_date", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'historical'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("cycle", "election_type", "state_id", name="uq_election_unique"),
    )
    op.create_index("ix_elections_cycle_type", "elections", ["cycle", "election_type"])
    op.create_index("ix_elections_irev_id", "elections", ["irev_election_id"])

    op.create_table(
        "candidates",
        sa.Column("candidate_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "election_id",
            sa.BigInteger(),
            sa.ForeignKey("elections.election_id"),
            nullable=False,
        ),
        sa.Column("party_id", sa.Integer(), sa.ForeignKey("parties.party_id"), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("is_incumbent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.UniqueConstraint("election_id", "party_id", name="uq_candidate_election_party"),
    )

    op.create_table(
        "ingestion_sources",
        sa.Column("source_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("license", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "election_results",
        sa.Column("result_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "election_id",
            sa.BigInteger(),
            sa.ForeignKey("elections.election_id"),
            nullable=False,
        ),
        sa.Column(
            "pu_id", sa.BigInteger(), sa.ForeignKey("polling_units.pu_id"), nullable=True
        ),
        sa.Column("lga_id", sa.BigInteger(), sa.ForeignKey("lgas.lga_id"), nullable=True),
        sa.Column(
            "state_id",
            sa.SmallInteger(),
            sa.ForeignKey("states.state_id"),
            nullable=True,
        ),
        sa.Column("aggregation", sa.Text(), nullable=False),
        sa.Column("party_id", sa.Integer(), sa.ForeignKey("parties.party_id"), nullable=False),
        sa.Column("votes", sa.Integer(), nullable=False),
        sa.Column("accredited_voters", sa.Integer(), nullable=True),
        sa.Column("registered_voters", sa.Integer(), nullable=True),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("ingestion_sources.source_id"),
            nullable=False,
        ),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("raw_json", JSONB(), nullable=True),
    )
    op.create_index(
        "ix_results_election_party", "election_results", ["election_id", "party_id"]
    )
    op.create_index("ix_results_state", "election_results", ["state_id"])
    op.create_index("ix_results_aggregation", "election_results", ["aggregation"])

    op.create_table(
        "scrape_log",
        sa.Column("log_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("phase", sa.Text(), nullable=True),
        sa.Column("state_id", sa.SmallInteger(), nullable=True),
        sa.Column("election_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "election_calendar",
        sa.Column("calendar_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("election_date", sa.Date(), nullable=False),
        sa.Column("election_type", sa.Text(), nullable=False),
        sa.Column(
            "state_id",
            sa.SmallInteger(),
            sa.ForeignKey("states.state_id"),
            nullable=True,
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'scheduled'")),
        sa.Column("inec_published_at", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_calendar_date_status", "election_calendar", ["election_date", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_calendar_date_status", table_name="election_calendar")
    op.drop_table("election_calendar")
    op.drop_table("scrape_log")
    op.drop_index("ix_results_aggregation", table_name="election_results")
    op.drop_index("ix_results_state", table_name="election_results")
    op.drop_index("ix_results_election_party", table_name="election_results")
    op.drop_table("election_results")
    op.drop_table("ingestion_sources")
    op.drop_table("candidates")
    op.drop_index("ix_elections_irev_id", table_name="elections")
    op.drop_index("ix_elections_cycle_type", table_name="elections")
    op.drop_table("elections")
    op.drop_table("parties")
    op.drop_table("polling_units")
    op.drop_table("wards")
    op.drop_table("lgas")
    op.drop_table("states")
