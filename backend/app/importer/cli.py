"""Historical importer CLI.

Usage examples:

    python -m app.importer.cli load \
        --file data/historical/2023_presidential_state.csv \
        --cycle 2023 --type presidential --aggregation state \
        --source stears_2023 --license proprietary

    python -m app.importer.cli load-excel-candidates \
        --file FCT_2026_Area_Council_Elections.xlsx \
        --cycle 2026 --state FC
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

from app.config import Config
from app.db import init_engine

log = logging.getLogger(__name__)


@click.group()
def cli() -> None:
    cfg = Config.from_env()
    init_engine(cfg.database_url)
    logging.basicConfig(level=getattr(logging, cfg.log_level.upper(), logging.INFO))


@cli.command()
@click.option("--file", "filepath", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--cycle", type=int, required=True)
@click.option("--type", "election_type", type=str, required=True)
@click.option("--aggregation", type=click.Choice(["pu", "ward", "lga", "state", "national"]), required=True)
@click.option("--source", "source_name", type=str, required=True)
@click.option("--license", "source_license", type=str, default="unknown")
@click.option("--url", "source_url", type=str, default="")
def load(
    filepath: Path,
    cycle: int,
    election_type: str,
    aggregation: str,
    source_name: str,
    source_license: str,
    source_url: str,
) -> None:
    """Load a CSV of results."""
    from app.importer.loaders.generic_csv import load_csv

    summary = load_csv(
        filepath=filepath,
        cycle=cycle,
        election_type=election_type,
        aggregation=aggregation,  # type: ignore[arg-type]
        source_name=source_name,
        source_license=source_license,
        source_url=source_url,
    )
    click.echo(json.dumps(summary.model_dump(), indent=2))
    if summary.unmapped_parties:
        click.echo(
            f"\nUnmapped parties ({len(summary.unmapped_parties)}): re-run after extending HISTORICAL_MAPPING.",
            err=True,
        )
        sys.exit(2)


@cli.command("load-excel-candidates")
@click.option("--file", "filepath", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--cycle", type=int, required=True)
@click.option("--state", "state_code", type=str, required=True)
def load_excel_candidates(filepath: Path, cycle: int, state_code: str) -> None:
    """Load the FCT-style candidate Excel sheet."""
    from app.importer.loaders.excel_candidates import load_excel

    summary = load_excel(filepath=filepath, cycle=cycle, state_code=state_code)
    click.echo(json.dumps(summary.model_dump(), indent=2))


if __name__ == "__main__":
    cli()
