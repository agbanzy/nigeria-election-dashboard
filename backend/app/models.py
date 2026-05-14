"""SQLAlchemy ORM models — unified schema across all cycles + election types.

See `/Users/godwinagbane/.claude/plans/logical-giggling-puzzle.md` section 3 for the design.
Alembic migration `0001_initial.py` is the canonical DDL source.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CHAR,
    Date,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime

from app.db import Base


class State(Base):
    __tablename__ = "states"

    state_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(CHAR(2), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    zone: Mapped[str] = mapped_column(Text, nullable=False)  # NC|NE|NW|SE|SS|SW

    lgas: Mapped[list["Lga"]] = relationship(back_populates="state", lazy="selectin")


class Lga(Base):
    __tablename__ = "lgas"

    lga_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    state_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("states.state_id"), nullable=False
    )
    irev_lga_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    lga_kind: Mapped[str] = mapped_column(Text, default="lga", nullable=False)  # 'lga'|'area_council'

    __table_args__ = (UniqueConstraint("state_id", "name", name="uq_lga_state_name"),)

    state: Mapped[State] = relationship(back_populates="lgas")
    wards: Mapped[list["Ward"]] = relationship(back_populates="lga", lazy="selectin")


class Ward(Base):
    __tablename__ = "wards"

    ward_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lga_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("lgas.lga_id"), nullable=False)
    irev_ward_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)

    lga: Mapped[Lga] = relationship(back_populates="wards")
    polling_units: Mapped[list["PollingUnit"]] = relationship(back_populates="ward", lazy="selectin")


class PollingUnit(Base):
    __tablename__ = "polling_units"

    pu_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ward_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("wards.ward_id"), nullable=False)
    irev_pu_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pu_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    registered_voters: Mapped[int | None] = mapped_column(Integer, nullable=True)

    ward: Mapped[Ward] = relationship(back_populates="polling_units")


class Party(Base):
    __tablename__ = "parties"

    party_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    color_hex: Mapped[str | None] = mapped_column(CHAR(7), nullable=True)
    active_from: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    active_to: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    __table_args__ = (UniqueConstraint("code", "active_from", name="uq_party_code_from"),)


class Election(Base):
    __tablename__ = "elections"

    election_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cycle: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    election_type: Mapped[str] = mapped_column(Text, nullable=False)
    state_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("states.state_id"), nullable=True
    )
    irev_election_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    election_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="historical", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("cycle", "election_type", "state_id", name="uq_election_unique"),
        Index("ix_elections_cycle_type", "cycle", "election_type"),
        Index("ix_elections_irev_id", "irev_election_id"),
    )


class Candidate(Base):
    __tablename__ = "candidates"

    candidate_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    election_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("elections.election_id"), nullable=False
    )
    party_id: Mapped[int] = mapped_column(Integer, ForeignKey("parties.party_id"), nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    is_incumbent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("election_id", "party_id", name="uq_candidate_election_party"),
    )


class IngestionSource(Base):
    __tablename__ = "ingestion_sources"

    source_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    license: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ElectionResult(Base):
    __tablename__ = "election_results"

    result_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    election_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("elections.election_id"), nullable=False
    )
    pu_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("polling_units.pu_id"), nullable=True
    )
    lga_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("lgas.lga_id"), nullable=True
    )
    state_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("states.state_id"), nullable=True
    )
    aggregation: Mapped[str] = mapped_column(Text, nullable=False)  # pu|ward|lga|state|national
    party_id: Mapped[int] = mapped_column(Integer, ForeignKey("parties.party_id"), nullable=False)
    votes: Mapped[int] = mapped_column(Integer, nullable=False)
    accredited_voters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    registered_voters: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ingestion_sources.source_id"), nullable=False
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_results_election_party", "election_id", "party_id"),
        Index("ix_results_state", "state_id"),
        Index("ix_results_aggregation", "aggregation"),
    )


class ScrapeLog(Base):
    __tablename__ = "scrape_log"

    log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    phase: Mapped[str | None] = mapped_column(Text, nullable=True)
    state_id: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    election_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ElectionCalendar(Base):
    __tablename__ = "election_calendar"

    calendar_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    election_date: Mapped[date] = mapped_column(Date, nullable=False)
    election_type: Mapped[str] = mapped_column(Text, nullable=False)
    state_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("states.state_id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        Text, default="scheduled", nullable=False
    )  # scheduled|live|completed|cancelled
    inec_published_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_calendar_date_status", "election_date", "status"),
    )
