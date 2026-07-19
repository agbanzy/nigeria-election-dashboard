"""CLI to OCR a batch of polling-unit result sheets.

Phase-D entry point. Iterates polling_units whose `document.url` is set
(from IReV scrape) but for which we don't yet have an OCR result, downloads
the image, runs `parse_ec8a_image`, and writes per-party ElectionResult
rows.

Usage:

    python -m app.ocr.batch --election <election_id> --limit 100
    python -m app.ocr.batch --state IM --cycle 2023 --limit 50
    python -m app.ocr.batch --dry-run --election 6 --limit 5    # just print

OCR is expensive (~2-5s/image). The --limit guard prevents runaway runs;
typical batch is 50-200 PUs. Re-runs are idempotent: PUs already in
ocr_results.status='success' are skipped.
"""

from __future__ import annotations

import argparse
import logging

import requests
from sqlalchemy import select

from app.config import Config
from app.db import init_engine, session_scope
from app.models import (
    Election,
    IngestionSource,
    PollingUnit,
    State,
    Ward,
)

log = logging.getLogger(__name__)

OCR_SOURCE_NAME = "ocr_ec8a"


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch OCR EC8A result sheets")
    parser.add_argument("--election", type=int, help="election_id to process")
    parser.add_argument("--state", type=str, help="state code (e.g. IM)")
    parser.add_argument("--cycle", type=int, help="cycle year filter")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg = Config.from_env()
    init_engine(cfg.database_url)
    logging.basicConfig(level=getattr(logging, cfg.log_level.upper(), logging.INFO))

    target_elections = _resolve_targets(args)
    log.info("ocr: target elections: %s", target_elections)
    if not target_elections:
        log.warning("ocr: no elections match filters")
        return

    processed = 0
    success = 0
    for eid in target_elections:
        if processed >= args.limit:
            break
        n = _process_election(eid, dry_run=args.dry_run, remaining=args.limit - processed)
        success += n["success"]
        processed += n["touched"]

    log.info("ocr: done. touched=%d success=%d", processed, success)


def _resolve_targets(args) -> list[int]:  # type: ignore[no-untyped-def]
    with session_scope() as session:
        if args.election:
            return [args.election]
        stmt = select(Election.election_id)
        if args.state:
            state = session.scalar(select(State).where(State.code == args.state.upper()))
            if state is None:
                return []
            stmt = stmt.where(Election.state_id == state.state_id)
        if args.cycle:
            stmt = stmt.where(Election.cycle == args.cycle)
        return list(session.scalars(stmt))


def _process_election(election_id: int, *, dry_run: bool, remaining: int) -> dict[str, int]:
    touched = 0
    success = 0
    with session_scope() as session:
        # Pull PUs that have a document URL in raw_json but no recorded OCR result.
        # The raw_json was written by the scraper; document.url is its image link.
        # For simplicity in this skeleton we just iterate all PUs of all wards under
        # this election's state — production batch would be smarter (track per-PU).
        elec = session.get(Election, election_id)
        if elec is None or elec.state_id is None:
            log.warning("ocr: election %s missing or has no state_id", election_id)
            return {"touched": 0, "success": 0}

        # Naive: walk all PUs of this state. Future: persist per-PU OCR status.
        stmt = (
            select(PollingUnit, Ward)
            .join(Ward, Ward.ward_id == PollingUnit.ward_id)
            .join(Election, Election.election_id == election_id)
            .where(Election.state_id == elec.state_id)
            .limit(remaining)
        )
        rows = list(session.execute(stmt))
        log.info("ocr: election=%s candidate PUs: %d", election_id, len(rows))

        # In this skeleton, we don't have the document URL per (election, PU);
        # the legacy storage was raw_json on the polling_units table. The new
        # schema doesn't track that yet. Real Phase-D work: extend the scraper
        # to record document URLs per (election, PU) and walk them here.
        # For now this is a no-op marker run.
        for _pu, _ward in rows[:remaining]:
            touched += 1

    return {"touched": touched, "success": success}


def _download(url: str, *, timeout: int = 30) -> bytes | None:
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        return r.content
    except Exception as exc:
        log.warning("ocr: download failed for %s: %s", url, exc)
        return None


def _ensure_ocr_source(session) -> IngestionSource:  # type: ignore[no-untyped-def]
    src = session.scalar(select(IngestionSource).where(IngestionSource.name == OCR_SOURCE_NAME))
    if src:
        return src
    src = IngestionSource(
        name=OCR_SOURCE_NAME,
        url="https://www.inecelectionresults.ng/",
        license="public-domain",
        notes="OCR of INEC EC8A result-sheet scans",
    )
    session.add(src)
    session.flush()
    return src


if __name__ == "__main__":
    main()
