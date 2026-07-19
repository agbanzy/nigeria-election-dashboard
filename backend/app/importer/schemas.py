"""Pydantic schemas for the historical importer.

Every row a loader produces must conform to one of these. Validation errors
abort the import — silent skips would let bad data into the dataset.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Aggregation = Literal["pu", "ward", "lga", "state", "national"]


class ResultRow(BaseModel):
    """One row of vote results at some aggregation level."""

    state_code: str = Field(
        min_length=2,
        max_length=2,
        description="ISO-like 2-letter (e.g. 'FC'); use 'NG' for nation-level rows",
    )
    lga_name: str | None = None
    ward_name: str | None = None
    pu_code: str | None = None
    party_code: str = Field(min_length=1, max_length=16)
    votes: int = Field(ge=0)
    accredited: int | None = Field(default=None, ge=0)
    registered: int | None = Field(default=None, ge=0)
    candidate_name: str | None = None
    is_incumbent: bool = False
    cycle: int = Field(ge=1999, le=2050)
    election_type: str
    aggregation: Aggregation

    @model_validator(mode="after")
    def check_aggregation_consistency(self) -> ResultRow:
        # Tighter rules: aggregations require lower-level fields to be present.
        if self.aggregation == "pu" and not self.pu_code:
            raise ValueError("aggregation='pu' requires pu_code")
        if self.aggregation in ("ward", "pu") and not self.ward_name:
            raise ValueError("aggregation='ward' or 'pu' requires ward_name")
        if self.aggregation in ("lga", "ward", "pu") and not self.lga_name:
            raise ValueError("aggregation requires lga_name")
        return self


class CandidateRow(BaseModel):
    cycle: int = Field(ge=1999, le=2050)
    election_type: str
    state_code: str | None = None
    party_code: str
    full_name: str
    is_incumbent: bool = False


class ImportSummary(BaseModel):
    rows_in: int
    rows_imported: int
    rows_skipped: int
    elections_touched: int
    unmapped_parties: list[str]
    errors: list[str]
