"""Test the generic CSV importer end-to-end."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def test_csv_import_state_level(db_engine, tmp_path: Path):
    from app.importer.loaders.generic_csv import load_csv
    from app.seed import seed

    seed()

    csv_path = tmp_path / "2023_pres.csv"
    csv_path.write_text(
        "state_code,lga_name,party_code,votes,accredited,registered,candidate_name\n"
        "LA,,APC,572606,1259853,7060195,Bola Tinubu\n"
        "LA,,LP,582454,1259853,7060195,Peter Obi\n"
        "LA,,PDP,75750,1259853,7060195,Atiku Abubakar\n"
    )

    summary = load_csv(
        filepath=csv_path,
        cycle=2023,
        election_type="presidential",
        aggregation="state",
        source_name="test_fixture",
        source_license="public",
        source_url="https://example.invalid",
    )
    assert summary.rows_in == 3
    assert summary.rows_imported == 3
    assert summary.rows_skipped == 0
    assert summary.unmapped_parties == []


def test_csv_import_rejects_unknown_state(db_engine, tmp_path: Path):
    from app.importer.loaders.generic_csv import load_csv
    from app.seed import seed

    seed()

    csv_path = tmp_path / "bad.csv"
    csv_path.write_text(
        "state_code,lga_name,party_code,votes,candidate_name\n"
        "ZZ,,APC,100,X\n"
    )
    summary = load_csv(
        filepath=csv_path,
        cycle=2023,
        election_type="presidential",
        aggregation="state",
        source_name="test_bad_state",
        source_license="public",
        source_url="",
    )
    assert summary.rows_imported == 0
    assert summary.rows_skipped == 1
    assert any("unknown state_code" in e for e in summary.errors)
