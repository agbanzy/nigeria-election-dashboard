"""One-shot CLI to ingest the bundled curated historical CSVs.

Run as: `python -m app.importer.loaders.seed_historical`

Idempotent — uses `ingestion_sources.name` to skip already-loaded files.
Bundled data (see backend/data/historical/) contains INEC-certified results
for top-of-ticket races where they're public-domain and accuracy can be
verified against multiple sources.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select

from app.config import Config
from app.db import init_engine, session_scope
from app.importer.loaders.generic_csv import load_csv
from app.models import IngestionSource

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "historical"

# (filename, cycle, election_type, aggregation, source_name, license, url, notes)
DATASETS: list[tuple[str, int, str, str, str, str, str, str]] = [
    (
        "2023_presidential_national.csv",
        2023,
        "presidential",
        "national",
        "inec_official_2023_pres",
        "public-domain",
        "https://www.inecnigeria.org/elections/election-results/",
        "INEC-certified national totals for the 2023 Presidential election",
    ),
    (
        "2023_governorship_state.csv",
        2023,
        "governorship",
        "state",
        "inec_official_2023_gov",
        "public-domain",
        "https://www.inecnigeria.org/elections/election-results/",
        "INEC-certified state totals for the 2023 off-cycle Governorship races (IM, KO, BY)",
    ),
    (
        "2024_governorship_state.csv",
        2024,
        "governorship",
        "state",
        "inec_official_2024_gov",
        "public-domain",
        "https://www.inecnigeria.org/elections/election-results/",
        "INEC-certified state totals for the 2024 off-cycle Governorship races (ED, ON)",
    ),
]


def main() -> None:
    cfg = Config.from_env()
    init_engine(cfg.database_url)
    logging.basicConfig(level=getattr(logging, cfg.log_level.upper(), logging.INFO))

    for filename, cycle, etype, agg, source_name, lic, url, notes in DATASETS:
        path = DATA_DIR / filename
        if not path.exists():
            log.warning("seed_historical: missing file %s, skipping", path)
            continue

        # Skip if source already ingested (idempotent).
        with session_scope() as session:
            existing = session.scalar(
                select(IngestionSource).where(IngestionSource.name == source_name)
            )
            if existing is not None:
                log.info("seed_historical: %s already ingested, skipping", source_name)
                continue

        log.info("seed_historical: loading %s", filename)
        summary = load_csv(
            filepath=path,
            cycle=cycle,
            election_type=etype,
            aggregation=agg,  # type: ignore[arg-type]
            source_name=source_name,
            source_license=lic,
            source_url=url,
        )
        log.info(
            "seed_historical: %s -> imported=%d skipped=%d unmapped=%s errors=%s",
            filename,
            summary.rows_imported,
            summary.rows_skipped,
            summary.unmapped_parties,
            summary.errors[:5],
        )

        # Patch notes on the source row.
        if summary.rows_imported > 0:
            with session_scope() as session:
                src = session.scalar(
                    select(IngestionSource).where(IngestionSource.name == source_name)
                )
                if src and not src.notes:
                    src.notes = notes


if __name__ == "__main__":
    main()
